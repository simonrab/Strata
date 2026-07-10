"""Search -> screen -> include: the eligibility gate that makes this a review.

A meta-analysis's credibility lives in the screening step: pooling every trial a
free-text search returns is a pooling engine, not a systematic review. This
module sits between retrieval and extraction and decides, per candidate, whether
it is eligible for the question.

Division of labour (CLAUDE.md):

1. A deterministic pre-filter removes what code can judge with certainty — a
   trial CT.gov explicitly records as non-interventional or non-randomized. It
   never excludes on *absent* metadata: benefit of the doubt passes the trial on
   to the clinical read (the demo fixtures carry no designModule and must stay
   eligible).
2. Claude reads each remaining trial's population / intervention / comparator
   against the question and judges include/exclude with a reason and a source
   quote — it judges, it never computes.

Honest degradation: with no key the clinical read cannot run, so trials that
clear the deterministic filter are *auto-included* and marked `by_claude=False`
with a visible reason. The funnel then shows the screen ran in reduced mode
rather than pretending it screened. The include/exclude *rule* is always code;
Claude only supplies the clinical judgment.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import BaseModel

from .schema import EligibilityDecision, Provenance, Question

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_KEYLESS_REASON = (
    "Clinical eligibility screen unavailable (no model key) — auto-included, "
    "confirm manually."
)

_SYSTEM_HINT = (
    "You are screening a candidate randomized trial for a meta-analysis. Given the "
    "question's PICO and the trial's title and eligibility criteria, judge whether "
    "the trial is eligible — its population, intervention, and comparator must be "
    "close enough to the question that pooling it is clinically meaningful. Return "
    "`eligible` true/false, the PICO `domain` that fails when ineligible "
    "(population, intervention, comparator, or outcome), a one-sentence `reason`, "
    "and the exact `quote` from the eligibility text your call rests on. Judge "
    "only; do not compute anything. When in doubt, prefer to include."
)


class _ScreenJudged(BaseModel):
    """The per-trial eligibility judgment we ask Claude to return."""

    eligible: bool = True
    domain: str = ""  # population | intervention | comparator | outcome (when ineligible)
    reason: str = ""
    quote: str = ""


def _resolve_client(llm_client):
    if llm_client is not None:
        return llm_client
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            return anthropic.Anthropic()
        except Exception:
            return None
    return None


def _design(study: dict) -> tuple[str, str]:
    dm = study.get("protocolSection", {}).get("designModule", {})
    study_type = (dm.get("studyType") or "").upper()
    allocation = (dm.get("designInfo", {}) or {}).get("allocation") or ""
    return study_type, allocation.upper()


def _deterministic_reason(study: dict) -> str | None:
    """A reason to exclude on structured design alone, or None to pass on.

    Only fires when CT.gov *records* a design that disqualifies the trial —
    absent metadata is never a reason to exclude.
    """
    study_type, allocation = _design(study)
    if study_type and study_type != "INTERVENTIONAL":
        return f"Not an interventional trial (study type: {study_type.title()})."
    if allocation == "NON_RANDOMIZED":
        return "Not a randomized trial (allocation: non-randomized)."
    return None


def _source_url(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


def _trial_prompt(question: Question, study: dict) -> str:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    elig = ps.get("eligibilityModule", {})
    return (
        f"Question PICO: {question.pico.model_dump()}\n"
        f"Trial: {ident.get('briefTitle', '')}\n"
        f"Eligibility criteria: {str(elig.get('eligibilityCriteria', ''))[:1500]}"
    )


def _claude_screen(question: Question, nct: str, study: dict, client) -> EligibilityDecision:
    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        judged: _ScreenJudged = client.messages.parse(
            model=model,
            max_tokens=512,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": _trial_prompt(question, study)}],
            output_format=_ScreenJudged,
        ).parsed_output
        quote = (
            Provenance(trial_id=nct, snippet=judged.quote, source_url=_source_url(nct))
            if judged.quote
            else None
        )
        return EligibilityDecision(
            study_id=nct,
            decision="included" if judged.eligible else "excluded",
            reason=judged.reason,
            domain=(judged.domain or None) if not judged.eligible else None,
            quote=quote,
            by_claude=True,
        )
    except Exception:
        # A failed or malformed clinical read must not silently include or exclude:
        # auto-include so a real trial isn't dropped, but mark by_claude=False and
        # route to manual review so the funnel shows the read did not complete.
        return EligibilityDecision(
            study_id=nct,
            decision="included",
            reason="Eligibility read failed — auto-included, confirm manually.",
            by_claude=False,
        )


def screen_candidates(
    question: Question,
    studies_by_id: Mapping[str, dict],
    llm_client=None,
    overrides: Mapping[str, EligibilityDecision] | None = None,
) -> list[EligibilityDecision]:
    """Screen each fetched candidate for eligibility; one decision per study.

    Decisions follow the question's `trial_ids` order (then any extra fetched
    ids), so the PRISMA funnel and the ledger read deterministically. A
    deterministically-excluded trial never reaches the model.

    `overrides` are a reviewer's authoritative include/exclude calls, keyed by
    study id: where one exists it replaces the automated judgment outright (the
    human confirming or overriding the screen), so a re-run honours the sign-off.
    """
    overrides = overrides or {}
    ordered = [tid for tid in question.trial_ids if tid in studies_by_id]
    ordered += [tid for tid in studies_by_id if tid not in set(ordered)]

    client = _resolve_client(llm_client)
    decisions: list[EligibilityDecision] = []
    for nct in ordered:
        override = overrides.get(nct)
        if override is not None:
            decisions.append(override)
            continue

        study = studies_by_id[nct]

        det_reason = _deterministic_reason(study)
        if det_reason is not None:
            decisions.append(
                EligibilityDecision(
                    study_id=nct, decision="excluded", reason=det_reason, domain="design"
                )
            )
            continue

        if client is None:
            decisions.append(
                EligibilityDecision(
                    study_id=nct, decision="included", reason=_KEYLESS_REASON
                )
            )
            continue

        decisions.append(_claude_screen(question, nct, study, client))

    return decisions
