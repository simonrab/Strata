"""LiveMeta MCP server.

Exposes the review pipeline as five composable tools plus a full-run
orchestrator, so Claude (or any MCP client) can drive the workflow end to end:

    search_trials -> extract_effects -> validate -> pool          (compose it)
    run_review                                                    (or one-shot)
    update                                                        (living layer)

Every tool is a thin wrapper over the same core the FastAPI pipeline uses, so
the MCP surface and the web UI can never diverge. The model never does pooling
math — `pool` re-runs the deterministic validation gate and then hands validated
points to the stats engine. The ClinicalTrials.gov client and the snapshot store
are swappable via `set_client` / `set_store` (mirroring the API's dependency
override), which is how the tests drive everything offline.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..core import demo
from ..core import extract as extract_mod
from ..core import grade as grade_mod
from ..core import living as living_mod
from ..core import llm as llm_mod
from ..core import rob as rob_mod
from ..core import search as search_mod
from ..core import validate as validate_mod
from ..core.pipeline import repool_with_decisions, run_review_collect
from ..core.schema import (
    EffectMeasure,
    GradeAssessment,
    LeaveOneOutRow,
    PICO,
    PoolResult,
    Question,
    ReviewDecision,
    ReviewDiff,
    ReviewResult,
    RobAssessment,
    TrialCandidate,
    TrialExtraction,
    ValidationResult,
)
from ..core.sources.clinicaltrials import ClinicalTrialsClient
from ..core.stats import engine as stats_engine
from ..core.stats import sensitivity as sensitivity_mod
from ..core.store import SnapshotStore

mcp = FastMCP("livemeta")

# --- Dependency seams (overridden in tests to run offline) -------------------

_client: ClinicalTrialsClient | None = None
_store: SnapshotStore | None = None


def set_client(client: ClinicalTrialsClient) -> None:
    global _client
    _client = client


def get_client() -> ClinicalTrialsClient:
    global _client
    if _client is None:
        _client = ClinicalTrialsClient()
    return _client


def set_store(store: SnapshotStore) -> None:
    global _store
    _store = store


def get_store() -> SnapshotStore:
    global _store
    if _store is None:
        _store = SnapshotStore()
    return _store


def _resolve_question(question_id: str) -> Question:
    """Find the question to run: the locked demo, or the latest saved snapshot."""
    if question_id == demo.GLP1_MACE_QUESTION.id:
        return demo.GLP1_MACE_QUESTION
    latest = get_store().load_latest(question_id)
    if latest is not None:
        return latest.question
    raise ValueError(f"Unknown question_id: {question_id!r}")


# --- Tools -------------------------------------------------------------------


@mcp.tool()
def search_trials(
    population: str,
    intervention: str,
    comparator: str,
    outcome: str,
    max_results: int = 20,
) -> list[TrialCandidate]:
    """Find candidate trials for a PICO question via ClinicalTrials.gov v2."""
    pico = PICO(
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcome=outcome,
    )
    return search_mod.search_trials(pico, max_results=max_results, client=get_client())


@mcp.tool()
def extract_effects(trial_id: str) -> TrialExtraction:
    """Extract the primary hazard ratio and CI for one trial, with provenance.

    Flags (rather than guesses) when the structured result is absent or
    incomplete.
    """
    study = get_client().fetch_study(trial_id)
    return extract_mod.extract_hr(study)


@mcp.tool()
def validate(extractions: list[dict]) -> list[ValidationResult]:
    """Run the deterministic validation gate over extracted effects.

    Accepts the extraction objects returned by `extract_effects`. Returns a
    pass/flag verdict per trial; anything flagged must not be pooled.
    """
    parsed = [TrialExtraction.model_validate(e) for e in extractions]
    return validate_mod.validate_ratio(parsed)


@mcp.tool()
def pool(extractions: list[dict], measure: str = "HR") -> PoolResult:
    """Pool validated effects with a random-effects meta-analysis (REML).

    Re-runs the deterministic gate and pools only the trials that pass — the
    model never selects or computes the pooled numbers. Requires at least two
    valid trials.
    """
    parsed = [TrialExtraction.model_validate(e) for e in extractions]
    validations = validate_mod.validate_ratio(parsed)
    passed = {v.study_id for v in validations if v.passed}
    points = [e.point for e in parsed if e.study_id in passed and e.point]
    return stats_engine.pool(points, measure=EffectMeasure(measure))


@mcp.tool()
def parse_question(text: str) -> Question:
    """Structure a free-text clinical question into PICO + candidate trials.

    Claude reads and structures the question; ClinicalTrials.gov search fills in
    the candidate trial ids. The locked demo question resolves deterministically
    without a key, so the memorable demo always works.
    """
    return llm_mod.parse_question(text, search_client=get_client())


@mcp.tool()
def record_decision(
    question_id: str, study_id: str, decision: str, reason: str | None = None
) -> ReviewResult:
    """Record a human confirm/flag on one trial and re-pool the review.

    A *flag* removes the trial from the pool; a *confirm* records sign-off. The
    re-pool is snapshotted as a new version, so the audit trail is real — the
    model never edits numbers, it only re-runs the deterministic pool.
    """
    store = get_store()
    latest = store.load_latest(question_id)
    if latest is None:
        raise ValueError(
            f"No existing review for question_id {question_id!r}; run `run_review` first."
        )
    store.save_decision(
        question_id, ReviewDecision(study_id=study_id, decision=decision, reason=reason)
    )
    repooled = repool_with_decisions(latest, store.load_decisions(question_id))
    store.save_snapshot(repooled)
    return repooled


@mcp.tool()
def assess_rob(trial_id: str) -> RobAssessment:
    """Appraise one trial's risk of bias (RoB 2) across the five domains.

    Claude judges each domain with a source quote; the overall judgment is rolled
    up deterministically. Returns a PENDING assessment (never fabricated) when no
    model key is configured.
    """
    study = get_client().fetch_study(trial_id)
    return rob_mod.assess_rob(study)


@mcp.tool()
def leave_one_out(question_id: str) -> list[LeaveOneOutRow]:
    """Leave-one-out sensitivity for a saved review: re-pool omitting each trial."""
    latest = get_store().load_latest(question_id)
    if latest is None:
        raise ValueError(
            f"No existing review for question_id {question_id!r}; run `run_review` first."
        )
    validations = validate_mod.validate_ratio(latest.extractions)
    passed = {v.study_id for v in validations if v.passed}
    points = [e.point for e in latest.extractions if e.study_id in passed and e.point]
    return sensitivity_mod.leave_one_out(points, measure=latest.question.measure)


@mcp.tool()
def grade_outcome(question_id: str) -> GradeAssessment:
    """Rate GRADE certainty for a saved review's outcome (uses its pool + RoB)."""
    latest = get_store().load_latest(question_id)
    if latest is None or latest.pool is None:
        raise ValueError(
            f"No pooled review for question_id {question_id!r}; run `run_review` first."
        )
    return grade_mod.grade_outcome(latest.question, latest.pool, latest.rob)


@mcp.tool()
def run_review(question_id: str = "glp1-mace") -> ReviewResult:
    """Run the whole pipeline for a known question and snapshot the result.

    This is the one-shot path (retrieve -> extract -> validate -> pool) and it
    persists the result so `update` has a baseline to diff against.
    """
    question = _resolve_question(question_id)
    result = run_review_collect(question, get_client().fetch_study)
    get_store().save_snapshot(result)
    return result


@mcp.tool()
def update(question_id: str, new_trial_id: str) -> ReviewDiff:
    """Add a trial to an existing review, re-run, and diff against the previous.

    The living layer: returns the new pooled estimate, the added trial, and —
    the load-bearing signal — whether the conclusion changed (a flip in
    statistical significance or in the direction of effect). Shares its core with
    the REST update endpoint via `living.apply_update` so the two can't diverge.
    """
    return living_mod.apply_update(
        get_store(), question_id, new_trial_id, get_client().fetch_study
    )


def main() -> None:
    """Console-script entry point: serve the tools over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
