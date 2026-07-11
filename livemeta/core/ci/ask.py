"""The market-intelligence chat: a natural-language front door.

Two layers, keeping the trust story intact:
1. `route` — Claude (or a deterministic keyword fallback) maps free text to one
   tool plus its params. It picks the tool; it never computes figures.
2. `answer` — deterministic code runs the chosen tool over the shared core and
   returns its typed payload plus a plain-language narrative whose numbers are
   quoted verbatim from that payload.

The router dispatches to *both* the existing noun-screens (landscape, company,
dossier, indication) and the new lenses (changes, compare, radar, moa), so the
hub is a real front door over everything.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel, Field

from . import changefeed, compare, moa, radar, service
from .schema import MarketAnswer, MarketQuery

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_TOOLS = "landscape | changes | compare | radar | moa | dossier | company | indication"

_SYSTEM_HINT = (
    "You route a pharma market-intelligence question to exactly one tool and "
    f"extract its parameters. Tools: {_TOOLS}. "
    "landscape = the asset x indication matrix for a condition; "
    "changes = what moved in a condition between two dates; "
    "compare = two named assets side by side; "
    "radar = upcoming trial readouts for a condition; "
    "moa = a condition's assets grouped by mechanism of action; "
    "dossier = everything about one asset; "
    "company = one sponsor's whole pipeline; "
    "indication = an indication broken into sub-populations. "
    "Fill condition, assets (drug names), indication, sponsor, since/until (ISO "
    "dates), horizon_months as relevant; leave the rest null. Set confidence."
)


@dataclass
class MarketDeps:
    """The search/data seams the answer layer needs — injected by the caller so
    the core stays offline-testable (fakes in, real clients in production)."""

    search_condition: Callable[[str], list[dict]] | None = None
    search_asset: Callable[[str], list[dict]] | None = None
    search_sponsor: Callable[[str], list[dict]] | None = None
    search_indication: Callable[[str], list[dict]] | None = None
    openfda: object | None = None
    llm_client: object | None = None


class _RouteRead(BaseModel):
    tool: str = "landscape"
    condition: str | None = None
    assets: list[str] = Field(default_factory=list)
    indication: str | None = None
    sponsor: str | None = None
    since: str | None = None
    until: str | None = None
    as_of: str | None = None
    horizon_months: int | None = None
    confidence: str = "low"


_VALID_TOOLS = {
    "landscape", "changes", "compare", "radar", "moa", "dossier", "company", "indication",
}


def _resolve_client(llm_client):
    if llm_client is not None:
        return llm_client
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - only with a real key
            import anthropic

            return anthropic.Anthropic()
        except Exception:
            return None
    return None


def _fallback_route(text: str) -> MarketQuery:
    """A no-key keyword router — enough to demo offline and to ground tests."""
    t = text.lower().strip()

    m = re.search(r"compare\s+(.+?)\s+(?:and|vs\.?|versus)\s+(.+?)[\?\.]?$", t)
    m = m or re.search(r"^(.+?)\s+(?:vs\.?|versus)\s+(.+?)[\?\.]?$", t)
    if m:
        return MarketQuery(
            tool="compare",
            assets=[m.group(1).strip().title(), m.group(2).strip().title()],
            reason="matched a 'compare X and Y' pattern",
        )

    if any(w in t for w in ("changed", "what moved", "what's new", "whats new", "since ")):
        return MarketQuery(tool="changes", condition=_strip_condition(text), reason="asks what changed")
    if any(w in t for w in ("readout", "upcoming", "expected", "radar", "calendar")):
        return MarketQuery(tool="radar", condition=_strip_condition(text), reason="asks about timing")
    if any(w in t for w in ("mechanism", "class", "moa", "modality")):
        return MarketQuery(tool="moa", condition=_strip_condition(text), reason="asks by mechanism")
    if "pipeline" in t:
        return MarketQuery(tool="company", sponsor=_strip_condition(text), reason="asks for a pipeline")
    if t.startswith(("about ", "dossier")):
        return MarketQuery(tool="dossier", assets=[_strip_condition(text).title()], reason="asks about one asset")

    return MarketQuery(tool="landscape", condition=_strip_condition(text), reason="default: map the landscape")


_STOP = re.compile(
    r"\b(what|changed|has|since|in|the|for|show|me|map|landscape|of|about|"
    r"upcoming|readouts|readout|pipeline|mechanism|class|by|whats|what's|new|"
    r"who|is|are|leading|ahead)\b",
    re.I,
)


def _strip_condition(text: str) -> str:
    """Best-effort condition/subject phrase from free text (fallback router only)."""
    cleaned = _STOP.sub(" ", text)
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-\+]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or text.strip()


def route(text: str, *, llm_client=None) -> MarketQuery:
    """Free text -> a structured routing intent. LLM when available, else keywords."""
    client = _resolve_client(llm_client)
    if client is not None:
        try:
            read: _RouteRead = client.messages.parse(
                model=os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL),
                max_tokens=512,
                system=_SYSTEM_HINT,
                messages=[{"role": "user", "content": text}],
                output_format=_RouteRead,
            ).parsed_output
            if read.tool in _VALID_TOOLS:
                return MarketQuery(
                    tool=read.tool,
                    condition=read.condition,
                    assets=read.assets,
                    indication=read.indication,
                    sponsor=read.sponsor,
                    since=read.since,
                    until=read.until,
                    as_of=read.as_of,
                    horizon_months=read.horizon_months,
                    confidence=read.confidence,
                    reason="routed by Claude",
                )
        except Exception:
            pass
    return _fallback_route(text)


def _dump(model) -> dict:
    return model.model_dump(mode="json")


def answer(store, text: str, *, deps: MarketDeps | None = None) -> MarketAnswer:
    """Route the question, run the chosen deterministic tool, narrate the result."""
    deps = deps or MarketDeps()
    q = route(text, llm_client=deps.llm_client)
    condition = q.condition or _strip_condition(text)

    if q.tool == "changes":
        diff = changefeed.landscape_changes(
            store, condition, since=q.since, until=q.until,
            search_pipeline=deps.search_condition,
        )
        result, narrative = _dump(diff), (
            f"{len(diff.changes)} competitive move(s) in {condition} "
            f"between {q.since or 'the start'} and {q.until or 'now'}."
        )
        suggestions = [f"Compare the top two assets in {condition}", f"Upcoming readouts in {condition}"]

    elif q.tool == "radar":
        rad = radar.milestone_radar(
            store, condition, search=deps.search_condition,
            horizon_months=q.horizon_months or 18, as_of=q.as_of,
        )
        result, narrative = _dump(rad), (
            f"{len(rad.milestones)} expected readout(s) for {condition} "
            f"in the next {rad.horizon_months} months."
        )
        suggestions = [f"What changed in {condition} recently", f"Group {condition} by mechanism"]

    elif q.tool == "moa":
        ml = moa.moa_landscape(store, condition, search=deps.search_condition, llm_client=deps.llm_client)
        result, narrative = _dump(ml), (
            f"{len(ml.clusters)} mechanism(s) across the {condition} field."
        )
        suggestions = [f"Map the {condition} landscape", f"Upcoming readouts in {condition}"]

    elif q.tool == "compare" and len(q.assets) >= 2:
        cmp = compare.compare_assets(
            store, q.assets[:4], q.indication,
            search=deps.search_asset, openfda=deps.openfda, llm_client=deps.llm_client,
        )
        result, narrative = _dump(cmp), (
            f"Comparing {', '.join(q.assets[:4])} on stage, scale, geography, and timing."
        )
        suggestions = [f"What changed for {q.assets[0]}", f"Upcoming readouts for {q.assets[0]}"]

    elif q.tool == "company":
        sponsor = q.sponsor or condition
        cp = service.company_pipeline(store, sponsor, search=deps.search_sponsor, openfda=deps.openfda)
        result, narrative = _dump(cp), (
            f"{sponsor}: {len(cp.assets)} asset(s) across {len(cp.indications)} "
            f"indication(s), {len(cp.approvals)} approval(s)."
        )
        suggestions = [f"What changed for {sponsor}", f"Compare {sponsor}'s top two assets"]

    elif q.tool == "dossier" and q.assets:
        dossier = service.asset_dossier(
            store, q.assets[0], search=deps.search_asset, openfda=deps.openfda, llm_client=deps.llm_client
        )
        result, narrative = _dump(dossier), (
            f"{q.assets[0]}: {len(dossier.trials)} trial(s), {len(dossier.readouts)} readout(s)."
        )
        suggestions = [f"Upcoming readouts for {q.assets[0]}"]

    elif q.tool == "indication":
        imap = service.indication_map(
            store, q.indication or condition, search=deps.search_indication, llm_client=deps.llm_client
        )
        result, narrative = _dump(imap), (
            f"{q.indication or condition}: {len(imap.nodes)} sub-population(s)."
        )
        suggestions = [f"Map the {q.indication or condition} landscape"]

    else:  # landscape (default)
        q.tool = "landscape"
        ls = service.get_landscape(
            store, condition, as_of=q.as_of, search_pipeline=deps.search_condition
        )
        result, narrative = _dump(ls), (
            f"{len(ls.assets)} asset(s) across {len(ls.indications)} "
            f"indication(s) for {condition}."
        )
        suggestions = [
            f"What changed in {condition} recently",
            f"Upcoming readouts in {condition}",
            f"Group {condition} by mechanism",
        ]

    return MarketAnswer(
        text=text,
        intent=q,
        tool=q.tool,
        result=result,
        narrative=narrative,
        suggestions=suggestions,
        notes=list(result.get("notes", []) if isinstance(result, dict) else []),
    )
