"""GRADE certainty of evidence — code derives what it can, Claude judges the rest.

Per CLAUDE.md, much of GRADE is derivable from what the pipeline already computes:
inconsistency from I², imprecision from the confidence interval, risk of bias from
the RoB 2 roll-up. Claude judges indirectness and publication bias. We start at
High (RCT evidence), apply the summed downgrades, and record a rationale for every
one. With no key, the two judged domains default to not-serious and say so — we
never invent a downgrade.
"""

from __future__ import annotations

import os

from pydantic import BaseModel

from .pipeline import interpret_i2, pool_direction, pool_significant
from .schema import (
    EggerResult,
    GradeAssessment,
    GradeDomain,
    GradeRating,
    PoolResult,
    Question,
    RobAssessment,
    RobJudgment,
)
from .stats.publication_bias import egger_test

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_HINT = (
    "You are rating certainty of evidence with GRADE. Judge only two domains for "
    "this pooled outcome: indirectness (population/intervention/comparator/outcome "
    "match to the question) and publication bias. Rate each 'not_serious', "
    "'serious', or 'very_serious' and give a one-sentence rationale. Do not judge "
    "risk of bias, inconsistency, or imprecision — those are computed."
)

# Ordered so the SoF table and footnotes read in GRADE's canonical order.
_LADDER = [GradeRating.HIGH, GradeRating.MODERATE, GradeRating.LOW, GradeRating.VERY_LOW]


class _GradeJudged(BaseModel):
    """The two domains we ask Claude to judge."""

    indirectness: str = "not_serious"
    indirectness_rationale: str = ""
    publication_bias: str = "not_serious"
    publication_bias_rationale: str = ""


def _serious_to_downgrade(serious: str) -> int:
    return {"not_serious": 0, "serious": -1, "very_serious": -2}.get(serious, 0)


def _apply(start: GradeRating, total_downgrade: int) -> GradeRating:
    idx = min(len(_LADDER) - 1, max(0, -total_downgrade))
    return _LADDER[idx]


def _risk_of_bias_domain(rob: list[RobAssessment]) -> GradeDomain:
    assessed = [r for r in rob if r.overall != RobJudgment.PENDING]
    if not assessed:
        return GradeDomain(
            name="risk_of_bias",
            serious="not_serious",
            downgrade=0,
            rationale="Risk of bias not yet assessed for the included trials.",
        )
    if any(r.overall == RobJudgment.HIGH for r in assessed):
        return GradeDomain(
            name="risk_of_bias",
            serious="serious",
            downgrade=-1,
            rationale="At least one included trial is at high risk of bias (RoB 2).",
        )
    return GradeDomain(
        name="risk_of_bias",
        serious="not_serious",
        downgrade=0,
        rationale="Included trials are at low risk of bias across RoB 2 domains.",
    )


def _inconsistency_domain(pool: PoolResult) -> GradeDomain:
    band = interpret_i2(pool.i2)
    serious = band in ("substantial", "considerable")
    return GradeDomain(
        name="inconsistency",
        serious="serious" if serious else "not_serious",
        downgrade=-1 if serious else 0,
        rationale=(
            f"Heterogeneity was {band} (I² = {pool.i2:.0f}%)."
            + (" Point estimates diverge across trials." if serious else " Estimates are consistent.")
        ),
    )


def _imprecision_domain(pool: PoolResult) -> GradeDomain:
    significant = pool_significant(pool)
    return GradeDomain(
        name="imprecision",
        serious="not_serious" if significant else "serious",
        downgrade=0 if significant else -1,
        rationale=(
            "The 95% CI excludes no effect and is reasonably narrow."
            if significant
            else "The 95% CI crosses no effect, so the estimate is imprecise."
        ),
    )


def _egger_domain(egger: EggerResult) -> GradeDomain:
    """A deterministic publication-bias domain from Egger's test (k >= 10)."""
    serious = egger.p is not None and egger.p < 0.10
    detail = (
        f"Egger's test across {egger.k} studies: intercept "
        f"{egger.intercept:.2f}, p = {egger.p:.3f}. "
    )
    detail += (
        "Funnel-plot asymmetry suggests possible small-study effects / publication bias."
        if serious
        else "No significant funnel-plot asymmetry detected."
    )
    return GradeDomain(
        name="publication_bias",
        serious="serious" if serious else "not_serious",
        downgrade=-1 if serious else 0,
        rationale=detail,
        by_claude=False,
    )


def _judged_domains(question: Question, llm_client) -> tuple[GradeDomain, GradeDomain]:
    client = llm_client
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            client = anthropic.Anthropic()
        except Exception:
            client = None

    if client is None:
        note = "Not assessed — requires the model (no key configured)."
        return (
            GradeDomain(name="indirectness", by_claude=True, rationale=note),
            GradeDomain(name="publication_bias", by_claude=True, rationale=note),
        )

    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        content = (
            f"Question: {question.text}\nPICO: {question.pico.model_dump()}"
        )
        judged: _GradeJudged = client.messages.parse(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": content}],
            output_format=_GradeJudged,
        ).parsed_output
    except Exception:
        note = "Not assessed — model call failed."
        return (
            GradeDomain(name="indirectness", by_claude=True, rationale=note),
            GradeDomain(name="publication_bias", by_claude=True, rationale=note),
        )

    return (
        GradeDomain(
            name="indirectness",
            serious=judged.indirectness,
            downgrade=_serious_to_downgrade(judged.indirectness),
            rationale=judged.indirectness_rationale,
            by_claude=True,
        ),
        GradeDomain(
            name="publication_bias",
            serious=judged.publication_bias,
            downgrade=_serious_to_downgrade(judged.publication_bias),
            rationale=judged.publication_bias_rationale,
            by_claude=True,
        ),
    )


def grade_outcome(
    question: Question,
    pool: PoolResult,
    rob: list[RobAssessment],
    llm_client=None,
) -> GradeAssessment:
    """Rate certainty for one outcome and build a Summary-of-Findings line."""
    rob_d = _risk_of_bias_domain(rob)
    incon_d = _inconsistency_domain(pool)
    imprec_d = _imprecision_domain(pool)
    indir_d, claude_pubbias_d = _judged_domains(question, llm_client)

    # Publication bias: quantitative Egger's test when there are enough studies
    # (Cochrane needs >= 10), otherwise fall back to Claude's qualitative judgment.
    egger = egger_test(pool.studies)
    if egger.applicable:
        pubbias_d = _egger_domain(egger)
        pub_test = egger
    else:
        pubbias_d = claude_pubbias_d
        pub_test = None

    domains = [rob_d, incon_d, indir_d, imprec_d, pubbias_d]
    total = sum(d.downgrade for d in domains)
    certainty = _apply(GradeRating.HIGH, total)

    footnotes = [
        f"Downgraded for {d.name.replace('_', ' ')}: {d.rationale}"
        for d in domains
        if d.downgrade < 0
    ]

    est, lo, hi = pool.estimate, pool.ci_low, pool.ci_high
    direction = {"reduced": "reduced", "increased": "increased", "unchanged": "did not change"}[
        pool_direction(pool)
    ]
    sof_line = (
        f"{question.pico.intervention} {direction} {question.pico.outcome} "
        f"({pool.measure.value} {est:.2f}, 95% CI {lo:.2f}-{hi:.2f}; {pool.k} trials); "
        f"{certainty.value.replace('_', ' ')}-certainty evidence."
    )

    return GradeAssessment(
        outcome=question.pico.outcome,
        starting_level=GradeRating.HIGH,
        certainty=certainty,
        domains=domains,
        sof_line=sof_line,
        footnotes=footnotes,
        publication_bias_test=pub_test,
    )
