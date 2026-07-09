"""Risk of Bias (RoB 2) appraisal — Claude reads and judges, code rolls up.

Division of labour (CLAUDE.md): Claude judges each of the five RoB 2 domains and
quotes the source it relies on; deterministic code computes the *overall*
judgment from those five (never the model); a human confirms each domain, same as
an extracted number. With no key/model, we return an honest PENDING assessment
rather than fabricate — consistent with llm.py's degrade-don't-raise contract.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from pydantic import BaseModel

from .extract import _identity
from .schema import (
    Provenance,
    RobAssessment,
    RobDecision,
    RobDomain,
    RobJudgment,
)

# The five RoB 2 domains, in order (key, name).
ROB_DOMAINS: list[tuple[str, str]] = [
    ("D1", "Randomization process"),
    ("D2", "Deviations from intended interventions"),
    ("D3", "Missing outcome data"),
    ("D4", "Measurement of the outcome"),
    ("D5", "Selection of the reported result"),
]

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_HINT = (
    "You are appraising a randomized trial with the Cochrane RoB 2 tool. Judge the "
    "five domains in this exact order:\n"
    "1. Randomization process\n"
    "2. Deviations from intended interventions\n"
    "3. Missing outcome data\n"
    "4. Measurement of the outcome\n"
    "5. Selection of the reported result\n"
    "Return exactly these five domains in that order. For each, judge the risk of "
    "bias as 'low', 'some_concerns', or 'high', give a one-sentence rationale, and "
    "quote the exact sentence from the trial record that supports your judgment. "
    "Judge only — never compute an overall score, and never invent a quote."
)


class _RobDomainOut(BaseModel):
    """One domain as Claude returns it."""

    key: str
    name: str
    judgment: str  # low | some_concerns | high
    rationale: str = ""
    quote: str = ""


class _RobDomains(BaseModel):
    """The structured output we ask Claude to return."""

    domains: list[_RobDomainOut]


def _judgment(value: str) -> RobJudgment:
    try:
        return RobJudgment(value.lower())
    except ValueError:
        return RobJudgment.PENDING


def overall_judgment(domains: Sequence[RobDomain]) -> RobJudgment:
    """RoB 2 roll-up: worst domain drives the overall judgment.

    Any High -> High; else any Some concerns -> Some concerns; else all Low ->
    Low. If any domain is still Pending, the overall is Pending (not assessed).
    """
    judgments = {d.judgment for d in domains}
    if RobJudgment.PENDING in judgments:
        return RobJudgment.PENDING
    if RobJudgment.HIGH in judgments:
        return RobJudgment.HIGH
    if RobJudgment.SOME_CONCERNS in judgments:
        return RobJudgment.SOME_CONCERNS
    return RobJudgment.LOW


def _pending_assessment(study_id: str, label: str) -> RobAssessment:
    domains = [
        RobDomain(key=k, name=n, judgment=RobJudgment.PENDING) for (k, n) in ROB_DOMAINS
    ]
    return RobAssessment(
        study_id=study_id, label=label, domains=domains, overall=RobJudgment.PENDING
    )


def _study_for_rob(study: dict) -> dict:
    """A compact view of the trial for the model. RoB 2 judges design and conduct,
    not the raw results tables — and full CT.gov records reach ~600KB (every
    outcome measurement and baseline row), which overflows the model's input and
    fails the whole assessment. Keep the protocol plus participant flow (dropouts,
    for missing-outcome-data bias); drop the bulky results modules."""
    results = study.get("resultsSection", {})
    return {
        "protocolSection": study.get("protocolSection", {}),
        "resultsSection": {
            "participantFlowModule": results.get("participantFlowModule", {}),
        },
    }


def _llm_assess(study: dict, client, study_id: str, source_url: str) -> _RobDomains:
    model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
    response = client.messages.parse(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_HINT,
        messages=[{"role": "user", "content": str(_study_for_rob(study))}],
        output_format=_RobDomains,
    )
    return response.parsed_output


def assess_rob(study: dict, llm_client=None) -> RobAssessment:
    """Appraise one trial's risk of bias across the five RoB 2 domains.

    Returns a PENDING assessment (no fabricated judgments) when no client/key is
    available or the model call fails.
    """
    study_id, label = _identity(study)
    source_url = f"https://clinicaltrials.gov/study/{study_id}"

    client = llm_client
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            client = anthropic.Anthropic()
        except Exception:
            client = None

    if client is None:
        return _pending_assessment(study_id, label)

    try:
        parsed = _llm_assess(study, client, study_id, source_url)
    except Exception:
        return _pending_assessment(study_id, label)

    # Match the model's domains to our canonical D1-D5. The model returns the five
    # domains in order but names its keys freely (e.g. "bias_randomization" rather
    # than "D1"), so fall back to positional mapping when the keys don't line up —
    # otherwise every domain silently goes PENDING.
    by_key = {d.key: d for d in parsed.domains}
    positional = not any(k in by_key for k, _ in ROB_DOMAINS)
    domains: list[RobDomain] = []
    for i, (key, name) in enumerate(ROB_DOMAINS):
        if positional:
            out = parsed.domains[i] if i < len(parsed.domains) else None
        else:
            out = by_key.get(key)
        if out is None:
            domains.append(RobDomain(key=key, name=name, judgment=RobJudgment.PENDING))
            continue
        quote = (
            Provenance(trial_id=study_id, snippet=out.quote, source_url=source_url,
                       field=f"rob.{key}")
            if out.quote
            else None
        )
        domains.append(
            RobDomain(
                key=key,
                name=name,
                judgment=_judgment(out.judgment),
                rationale=out.rationale,
                source_quote=quote,
            )
        )

    return RobAssessment(
        study_id=study_id,
        label=label,
        domains=domains,
        overall=overall_judgment(domains),
    )


def apply_rob_decisions(
    assessment: RobAssessment, decisions: Sequence[RobDecision]
) -> RobAssessment:
    """Mark domains a human has signed off ("Verify"); roll up the assessment.

    A confirm records sign-off — it does not change the judgment or poolability.
    The assessment is `confirmed` once every domain has been signed off.
    """
    confirmed_keys = {
        d.domain_key for d in decisions if d.study_id == assessment.study_id
    }
    domains = [
        d.model_copy(update={"confirmed": d.confirmed or d.key in confirmed_keys})
        for d in assessment.domains
    ]
    return assessment.model_copy(
        update={
            "domains": domains,
            "confirmed": bool(domains) and all(d.confirmed for d in domains),
        }
    )
