"""End-to-end review pipeline: retrieve -> extract -> validate -> pool.

Yields PipelineEvents so the UI can stream progress. The data source is injected
(defaults to the live ClinicalTrials.gov client) so tests can drive it offline
from recorded fixtures.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from collections.abc import Sequence

from .schema import (
    EffectMeasure,
    PipelineEvent,
    PoolResult,
    Question,
    ReviewDecision,
    ReviewResult,
)
from .sources.clinicaltrials import ClinicalTrialsClient
from .stats import engine as stats_engine
from . import extract as extract_mod
from . import validate as validate_mod

FetchStudy = Callable[[str], dict]


def interpret_i2(i2: float) -> str:
    """Cochrane interpretation bands (avoid rigid thresholds)."""
    if i2 <= 40:
        return "might not be important"
    if i2 <= 60:
        return "moderate"
    if i2 <= 90:
        return "substantial"
    return "considerable"


def pool_direction(pool: PoolResult) -> str:
    """Direction of effect relative to no effect (ratio = 1)."""
    if pool.estimate < 1:
        return "reduced"
    if pool.estimate > 1:
        return "increased"
    return "unchanged"


def pool_significant(pool: PoolResult) -> bool:
    """Whether the confidence interval excludes no effect (does not cross 1)."""
    return pool.ci_high < 1 or pool.ci_low > 1


def summarize(question: Question, pool: PoolResult) -> str:
    """A plain-language, clinician-facing conclusion."""
    est, lo, hi = pool.estimate, pool.ci_low, pool.ci_high
    measure = pool.measure.value
    direction = {"reduced": "reduced", "increased": "increased", "unchanged": "did not change"}[
        pool_direction(pool)
    ]
    significant = pool_significant(pool)
    strength = "a statistically significant" if significant else "no statistically significant"
    interp = interpret_i2(pool.i2)
    ci_kind = "Hartung-Knapp" if pool.ci_method.value == "hksj" else "Wald"
    return (
        f"Pooling {pool.k} trials, {question.pico.intervention} {direction} "
        f"{question.pico.outcome} versus {question.pico.comparator}, with {strength} "
        f"effect: {measure} {est:.2f} (95% CI {lo:.2f}-{hi:.2f}, {ci_kind}). "
        f"Heterogeneity was {interp} (I² = {pool.i2:.0f}%, τ² = {pool.tau2:.3f})."
    )


def run_review(
    question: Question, fetch_study: FetchStudy | None = None
) -> Iterator[PipelineEvent]:
    fetch_study = fetch_study or ClinicalTrialsClient().fetch_study

    yield PipelineEvent(
        stage="parse",
        message="Parsed question into PICO.",
        data={"pico": question.pico.model_dump()},
    )
    yield PipelineEvent(
        stage="retrieve",
        message=f"Retrieving {len(question.trial_ids)} candidate trials.",
        data={"trial_ids": question.trial_ids},
    )

    extractions = []
    for nct in question.trial_ids:
        study = fetch_study(nct)
        ext = extract_mod.extract_hr(study)
        extractions.append(ext)
        msg = (
            f"{ext.label}: flagged for review ({ext.flag_reason})"
            if ext.flagged
            else f"{ext.label}: {ext.measure.value} {ext.hr} ({ext.ci_low}-{ext.ci_high})"
        )
        yield PipelineEvent(stage="extract", message=msg, data=ext.model_dump())

    validations = validate_mod.validate_ratio(extractions)
    passed_ids = {v.study_id for v in validations if v.passed}
    n_flagged = len(validations) - len(passed_ids)
    yield PipelineEvent(
        stage="validate",
        message=f"{len(passed_ids)} trials passed validation, {n_flagged} flagged.",
        data={"validations": [v.model_dump() for v in validations]},
    )

    points = [e.point for e in extractions if e.study_id in passed_ids and e.point]
    pool = stats_engine.pool(points, measure=question.measure) if len(points) >= 2 else None

    if pool is None:
        yield PipelineEvent(
            stage="done",
            message="Too few valid trials to pool — abstaining.",
            data=ReviewResult(
                question=question, extractions=extractions, validations=validations
            ).model_dump(),
        )
        return

    summary = summarize(question, pool)
    yield PipelineEvent(
        stage="pool",
        message=f"Pooled {pool.k} trials: {pool.measure.value} {pool.estimate:.2f} "
        f"({pool.ci_low:.2f}-{pool.ci_high:.2f}).",
        data=pool.model_dump(),
    )
    yield PipelineEvent(
        stage="done",
        message=summary,
        data=ReviewResult(
            question=question,
            extractions=extractions,
            validations=validations,
            pool=pool,
            summary=summary,
        ).model_dump(),
    )


def run_review_collect(
    question: Question, fetch_study: FetchStudy | None = None
) -> ReviewResult:
    """Drain the pipeline and return the final ReviewResult."""
    result = ReviewResult(question=question)
    for event in run_review(question, fetch_study):
        if event.stage == "done" and event.data is not None:
            result = ReviewResult.model_validate(event.data)
    return result


def repool_with_decisions(
    result: ReviewResult, decisions: Sequence[ReviewDecision]
) -> ReviewResult:
    """Re-pool a review after a human confirms or flags trials.

    A *flag* removes a trial from the pool (it fails the validation gate like any
    un-extracted trial); a *confirm* records sign-off but leaves poolability to the
    deterministic gate. The estimate, heterogeneity, and summary are recomputed
    from scratch — the model never edits numbers, it only re-runs the pool.
    """
    by_decision = {d.study_id: d for d in decisions}

    extractions = []
    for e in result.extractions:
        ext = e.model_copy(deep=True)
        decision = by_decision.get(ext.study_id)
        if decision is not None:
            if decision.decision == "flagged":
                ext.flagged = True
                ext.confirmed = False
                ext.flag_reason = decision.reason or "Flagged for review by a reviewer."
            elif decision.decision == "confirmed":
                ext.confirmed = True
                ext.flagged = False
                ext.flag_reason = None
        extractions.append(ext)

    validations = validate_mod.validate_ratio(extractions)
    passed_ids = {v.study_id for v in validations if v.passed}
    points = [e.point for e in extractions if e.study_id in passed_ids and e.point]

    pool = (
        stats_engine.pool(points, measure=result.question.measure)
        if len(points) >= 2
        else None
    )
    summary = (
        summarize(result.question, pool)
        if pool is not None
        else "Too few valid trials to pool — abstaining."
    )

    return ReviewResult(
        question=result.question,
        extractions=extractions,
        validations=validations,
        pool=pool,
        summary=summary,
    )
