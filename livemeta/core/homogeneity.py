"""Homogeneity / clinical-diversity gate — Claude judges, code decides.

The mandatory Cochrane expectation (CLAUDE.md): only pool studies judged similar
enough in population, intervention, comparator, and outcome to give a clinically
meaningful answer. This module surfaces two signals — Claude's clinical-diversity
read across the four PICO domains, and the deterministic statistical-heterogeneity
band (I²) — and decides whether the pipeline must stop and ask a human before
pooling.

Division of labour: Claude *judges* clinical diversity (it reads the trials); the
gate *rule* is deterministic. With no key, the clinical domains are left
un-judged (never fabricated), so the gate rests on the I² band alone — which
keeps the homogeneous demo pooling straight through.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from pydantic import BaseModel

from .pipeline import interpret_i2
from .schema import (
    DiversityAssessment,
    DiversityDomain,
    PoolResult,
    Question,
    TrialExtraction,
)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Statistical bands that, on their own, force a confirmation (Cochrane: I² above
# these ranges means real inconsistency worth pausing on).
_GATING_BANDS = {"substantial", "considerable"}

_PICO_KEYS = ["population", "intervention", "comparator", "outcome"]

_SYSTEM_HINT = (
    "You are judging clinical diversity across a set of randomized trials being "
    "considered for a meta-analysis. For each of the four PICO domains — "
    "population, intervention, comparator, outcome — judge whether the trials are "
    "'similar', 'mixed', or 'divergent' enough that pooling would still give a "
    "clinically meaningful answer, with a one-sentence rationale. Judge only; do "
    "not compute statistics. When in doubt, prefer 'mixed' over 'divergent'."
)


class _DiversityJudged(BaseModel):
    """The four PICO-domain judgments we ask Claude to return."""

    population: str = "not_assessed"
    population_rationale: str = ""
    intervention: str = "not_assessed"
    intervention_rationale: str = ""
    comparator: str = "not_assessed"
    comparator_rationale: str = ""
    outcome: str = "not_assessed"
    outcome_rationale: str = ""


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


def _unjudged_domains() -> list[DiversityDomain]:
    note = "Not assessed — requires the model (no key configured)."
    return [
        DiversityDomain(key=k, judgment="not_assessed", rationale=note, by_claude=True)
        for k in _PICO_KEYS
    ]


def _trial_digest(question: Question, studies: Sequence[dict]) -> str:
    """A compact description of the trials for the clinical-diversity judgment."""
    lines = [f"Question PICO: {question.pico.model_dump()}"]
    for s in studies:
        ident = s.get("protocolSection", {}).get("identificationModule", {})
        elig = s.get("protocolSection", {}).get("eligibilityModule", {})
        lines.append(
            f"- {ident.get('nctId', ident.get('id', '?'))}: "
            f"{ident.get('briefTitle', '')} | "
            f"eligibility: {str(elig.get('eligibilityCriteria', ''))[:300]}"
        )
    return "\n".join(lines)


def _clinical_domains(
    question: Question, studies: Sequence[dict], client
) -> list[DiversityDomain]:
    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        judged: _DiversityJudged = client.messages.parse(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": _trial_digest(question, studies)}],
            output_format=_DiversityJudged,
        ).parsed_output
    except Exception:
        return [
            DiversityDomain(
                key=k, judgment="not_assessed", rationale="Model read failed.", by_claude=True
            )
            for k in _PICO_KEYS
        ]

    return [
        DiversityDomain(
            key=k,
            judgment=getattr(judged, k, "not_assessed"),
            rationale=getattr(judged, f"{k}_rationale", ""),
            by_claude=True,
        )
        for k in _PICO_KEYS
    ]


def assess_diversity(
    question: Question,
    extractions: Sequence[TrialExtraction],
    studies: Sequence[dict],
    provisional_pool: PoolResult,
    llm_client=None,
) -> DiversityAssessment:
    """Judge whether this set is homogeneous enough to pool without sign-off.

    Fires the gate (`requires_confirmation=True`) when the statistical band is
    substantial/considerable, or when Claude judges any PICO domain 'divergent'.
    """
    i2 = provisional_pool.i2
    band = interpret_i2(i2)

    client = _resolve_client(llm_client)
    domains = _clinical_domains(question, studies, client) if client else _unjudged_domains()

    stat_gate = band in _GATING_BANDS
    clinical_gate = any(d.judgment == "divergent" for d in domains)
    requires = stat_gate or clinical_gate

    reasons = []
    if stat_gate:
        reasons.append(f"statistical heterogeneity is {band} (I² = {i2:.0f}%)")
    if clinical_gate:
        divergent = [d.key for d in domains if d.judgment == "divergent"]
        reasons.append("clinical diversity is high in " + ", ".join(divergent))
    if requires:
        rationale = (
            "Pooling withheld for confirmation because " + "; ".join(reasons) + "."
        )
    else:
        rationale = (
            f"Trials are similar enough to pool: heterogeneity is {band} "
            f"(I² = {i2:.0f}%) and no PICO domain is divergent."
        )

    return DiversityAssessment(
        domains=domains,
        i2=i2,
        i2_band=band,
        requires_confirmation=requires,
        confirmed=False,
        rationale=rationale,
    )
