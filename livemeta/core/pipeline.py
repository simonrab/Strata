"""End-to-end review pipeline: retrieve -> extract -> validate -> pool.

Yields PipelineEvents so the UI can stream progress. The data source is injected
(defaults to the live ClinicalTrials.gov client) so tests can drive it offline
from recorded fixtures.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

from .schema import (
    BinaryEffect,
    EffectMeasure,
    EffectPoint,
    GradeAssessment,
    LeaveOneOutRow,
    PipelineEvent,
    PoolResult,
    Provenance,
    Question,
    ReviewDecision,
    ReviewResult,
    RobAssessment,
    TrialExtraction,
)
from .sources.router import SourceRouter
from .stats import engine as stats_engine
from .stats import sensitivity as sensitivity_mod
from . import extract as extract_mod
from . import rob as rob_mod
from . import validate as validate_mod

FetchStudy = Callable[[str], dict]

# The two I/O-bound stages — CT.gov fetches and per-trial RoB calls — run over
# bounded worker pools instead of serially, so a broad candidate set no longer
# means a serial crawl. Bounds are deliberate: too many parallel CT.gov requests
# risk throttling the IP, and RoB concurrency stays modest for the model's rate
# limits.
_FETCH_CONCURRENCY = 8
_ROB_CONCURRENCY = 5


def _failed_extraction(nct: str, exc: Exception) -> TrialExtraction:
    """A flagged placeholder for a trial that couldn't be retrieved, so one bad
    fetch is dropped from the pool rather than aborting an otherwise-good run."""
    return TrialExtraction(
        study_id=nct,
        label=nct,
        flagged=True,
        flag_reason=f"Could not retrieve from ClinicalTrials.gov: {exc}",
        provenance=[
            Provenance(trial_id=nct, snippet="", source_url=f"https://clinicaltrials.gov/study/{nct}")
        ],
    )


def _effect_summary(ext: TrialExtraction) -> str:
    """A human-readable one-liner for an extraction, per its variant.

    Ratio (HR/RR/OR reported as ratio+CI) → `HR 0.86 (0.79-0.94)`; binary 2x2 →
    `12/500 vs 20/500`; continuous → `MD 2.00`.
    """
    if ext.binary is not None:
        b = ext.binary
        return f"{b.treatment.events}/{b.treatment.total} vs {b.control.events}/{b.control.total}"
    if ext.continuous is not None and ext.point is not None:
        return f"{ext.measure.value} {ext.point.yi:.2f}"
    if ext.hr is not None:
        return f"{ext.measure.value} {ext.hr} ({ext.ci_low}-{ext.ci_high})"
    return ext.measure.value


def _pool_inputs(
    extractions: Sequence[TrialExtraction], passed_ids: set[str]
) -> list[BinaryEffect | EffectPoint]:
    """The pooling inputs for the trials that passed validation.

    Binary variants are handed to the engine as `BinaryEffect` so it can route a
    sparse 2x2 table to Peto; everything else contributes its pre-computed
    `EffectPoint`. A review has a single measure, so these never mix within one
    pool (the engine's rare-event route requires all-binary inputs).
    """
    passed = [e for e in extractions if e.study_id in passed_ids]
    if passed and all(e.binary is not None for e in passed):
        return [e.binary for e in passed]
    return [e.point for e in passed if e.point]


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


def _assess_rob_concurrent(studies: Sequence[dict], llm_client) -> list[RobAssessment]:
    """RoB 2 for the pooled trials, run over a bounded pool but order-preserved."""
    if not studies:
        return []
    workers = min(_ROB_CONCURRENCY, len(studies))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda s: rob_mod.assess_rob(s, llm_client=llm_client), studies))


def _appraise(
    question: Question,
    pooled_studies: Sequence[dict],
    points: Sequence,
    pool: PoolResult,
    llm_client=None,
) -> tuple[list[RobAssessment], GradeAssessment, list[LeaveOneOutRow]]:
    """Run the three appraisal steps that follow a successful pool.

    RoB 2 runs only on the *pooled* trials — you appraise what you pool, not every
    candidate the search surfaced — concurrently and order-preserved. Plus a
    leave-one-out sensitivity view and a GRADE certainty rating. `grade` is
    imported here to avoid a module import cycle (grade reuses this module).
    """
    from . import grade as grade_mod

    rob = _assess_rob_concurrent(pooled_studies, llm_client)
    loo = sensitivity_mod.leave_one_out(points, measure=question.measure)
    grade = grade_mod.grade_outcome(question, pool, rob, llm_client=llm_client)
    return rob, grade, loo


def run_review(
    question: Question,
    fetch_study: FetchStudy | None = None,
    llm_client=None,
) -> Iterator[PipelineEvent]:
    fetch_study = fetch_study or SourceRouter().fetch

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

    # Fetch (I/O-bound) over a bounded thread pool rather than one-at-a-time, and
    # tolerate a per-trial retrieval failure instead of aborting the whole run.
    # Extractions are reassembled in the original order afterwards, so the pool,
    # forest plot, and tests stay deterministic regardless of completion timing.
    studies_by_id: dict[str, dict] = {}
    extractions_by_id: dict[str, TrialExtraction] = {}

    def _fetch(nct: str):
        try:
            return nct, fetch_study(nct), None
        except Exception as exc:  # reported per-trial below; never aborts the run
            return nct, None, exc

    workers = min(_FETCH_CONCURRENCY, max(1, len(question.trial_ids)))
    with ThreadPoolExecutor(max_workers=workers) as pool_ex:
        futures = [pool_ex.submit(_fetch, nct) for nct in question.trial_ids]
        for future in as_completed(futures):
            nct, study, err = future.result()
            if study is None:
                ext = _failed_extraction(nct, err)
            else:
                studies_by_id[nct] = study
                ext = extract_mod.extract_any(study, question.measure, llm_client=llm_client)
            extractions_by_id[nct] = ext
            msg = (
                f"{ext.label}: flagged for review ({ext.flag_reason})"
                if ext.flagged
                else f"{ext.label}: {_effect_summary(ext)}"
            )
            yield PipelineEvent(stage="extract", message=msg, data=ext.model_dump())

    extractions = [
        extractions_by_id[nct] for nct in question.trial_ids if nct in extractions_by_id
    ]

    validations = validate_mod.validate_extractions(extractions)
    passed_ids = {v.study_id for v in validations if v.passed}
    n_flagged = len(validations) - len(passed_ids)
    yield PipelineEvent(
        stage="validate",
        message=f"{len(passed_ids)} trials passed validation, {n_flagged} flagged.",
        data={"validations": [v.model_dump() for v in validations]},
    )

    inputs = _pool_inputs(extractions, passed_ids)
    provisional = (
        stats_engine.pool(inputs, measure=question.measure) if len(inputs) >= 2 else None
    )

    if provisional is None:
        yield PipelineEvent(
            stage="done",
            message="Too few valid trials to pool — abstaining.",
            data=ReviewResult(
                question=question, extractions=extractions, validations=validations
            ).model_dump(),
        )
        return

    # Homogeneity gate (mandatory): judge clinical diversity + statistical
    # heterogeneity before committing the pool. `homogeneity` is imported here to
    # avoid an import cycle (it reuses interpret_i2 from this module).
    from . import homogeneity as homogeneity_mod

    pooled_studies = [
        studies_by_id[p.study_id] for p in inputs if p.study_id in studies_by_id
    ]
    diversity = homogeneity_mod.assess_diversity(
        question, extractions, pooled_studies, provisional, llm_client=llm_client
    )
    yield PipelineEvent(
        stage="diversity",
        message=diversity.rationale,
        data=diversity.model_dump(),
    )

    if diversity.requires_confirmation and not diversity.confirmed:
        summary = "Pooling withheld pending homogeneity confirmation."
        yield PipelineEvent(
            stage="done",
            message=summary,
            data=ReviewResult(
                question=question,
                extractions=extractions,
                validations=validations,
                summary=summary,
                diversity=diversity,
            ).model_dump(),
        )
        return

    pool = provisional
    summary = summarize(question, pool)
    yield PipelineEvent(
        stage="pool",
        message=f"Pooled {pool.k} trials: {pool.measure.value} {pool.estimate:.2f} "
        f"({pool.ci_low:.2f}-{pool.ci_high:.2f}).",
        data=pool.model_dump(),
    )

    # Appraise only the trials that actually made the pool, in pool order.
    rob, grade, sensitivity = _appraise(
        question, pooled_studies, inputs, pool, llm_client=llm_client
    )
    n_pending = sum(1 for r in rob if r.overall.value == "pending")
    yield PipelineEvent(
        stage="appraise",
        message=(
            f"Risk of bias assessed for {len(rob)} trials"
            + (f" ({n_pending} pending — no model key)." if n_pending else ".")
        ),
        data={"rob": [r.model_dump() for r in rob]},
    )
    yield PipelineEvent(
        stage="sensitivity",
        message=f"Leave-one-out sensitivity across {len(sensitivity)} trials.",
        data={"sensitivity": [r.model_dump() for r in sensitivity]},
    )
    yield PipelineEvent(
        stage="grade",
        message=f"GRADE certainty: {grade.certainty.value.replace('_', ' ')}.",
        data={"grade": grade.model_dump()},
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
            rob=rob,
            grade=grade,
            sensitivity=sensitivity,
            diversity=diversity,
        ).model_dump(),
    )


def run_review_collect(
    question: Question, fetch_study: FetchStudy | None = None, llm_client=None
) -> ReviewResult:
    """Drain the pipeline and return the final ReviewResult."""
    result = ReviewResult(question=question)
    for event in run_review(question, fetch_study, llm_client=llm_client):
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

    validations = validate_mod.validate_extractions(extractions)
    passed_ids = {v.study_id for v in validations if v.passed}
    inputs = _pool_inputs(extractions, passed_ids)

    pool = (
        stats_engine.pool(inputs, measure=result.question.measure)
        if len(inputs) >= 2
        else None
    )
    summary = (
        summarize(result.question, pool)
        if pool is not None
        else "Too few valid trials to pool — abstaining."
    )

    # RoB judgments are per-trial and unaffected by a re-pool, so carry them over;
    # GRADE and the leave-one-out view depend on the pool, so recompute them.
    rob = [r.model_copy(deep=True) for r in result.rob]
    grade = result.grade
    loo: list[LeaveOneOutRow] = []
    if pool is not None:
        from . import grade as grade_mod

        grade = grade_mod.grade_outcome(result.question, pool, rob)
        loo = sensitivity_mod.leave_one_out(inputs, measure=result.question.measure)

    return ReviewResult(
        question=result.question,
        extractions=extractions,
        validations=validations,
        pool=pool,
        summary=summary,
        rob=rob,
        grade=grade,
        sensitivity=loo,
        diversity=result.diversity,
    )


def repool_with_diversity(result: ReviewResult, decision) -> ReviewResult:
    """Pool a review that was withheld at the homogeneity gate, once a human
    confirms the clinically diverse trials may be combined.

    The reviewer's sign-off flips `diversity.confirmed`; the pool, grade, and
    leave-one-out are then computed from the same validated extractions. The
    model never edits numbers — confirmation only lifts the gate. RoB is not
    re-derived here (it needs the source records); the living-layer update path
    re-runs the full appraisal.
    """
    from .schema import DiversityAssessment

    extractions = [e.model_copy(deep=True) for e in result.extractions]
    validations = validate_mod.validate_extractions(extractions)
    passed_ids = {v.study_id for v in validations if v.passed}
    inputs = _pool_inputs(extractions, passed_ids)

    pool = (
        stats_engine.pool(inputs, measure=result.question.measure)
        if len(inputs) >= 2
        else None
    )

    diversity = (result.diversity or DiversityAssessment()).model_copy(
        update={
            "confirmed": True,
            "rationale": (
                (result.diversity.rationale + " " if result.diversity else "")
                + "Confirmed by a reviewer: trials judged clinically combinable."
            ),
        }
    )

    if pool is None:
        return ReviewResult(
            question=result.question,
            extractions=extractions,
            validations=validations,
            summary="Too few valid trials to pool — abstaining.",
            diversity=diversity,
        )

    summary = summarize(result.question, pool)
    from . import grade as grade_mod

    rob = [r.model_copy(deep=True) for r in result.rob]
    grade = grade_mod.grade_outcome(result.question, pool, rob)
    loo = sensitivity_mod.leave_one_out(inputs, measure=result.question.measure)

    return ReviewResult(
        question=result.question,
        extractions=extractions,
        validations=validations,
        pool=pool,
        summary=summary,
        rob=rob,
        grade=grade,
        sensitivity=loo,
        diversity=diversity,
    )
