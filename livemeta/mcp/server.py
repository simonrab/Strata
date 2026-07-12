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

from ..core import extract as extract_mod
from ..core.ci import ask as ci_ask
from ..core.ci import changefeed as ci_changefeed
from ..core.ci import compare as ci_compare
from ..core.ci import moa as ci_moa
from ..core.ci import radar as ci_radar
from ..core.ci import service as ci_service
from ..core.ci.ask import MarketDeps
from ..core.ci.schema import (
    AssetComparison,
    AssetDossier,
    CompanyPipeline,
    DevelopmentEvent,
    IndicationMap,
    Landscape,
    LandscapeDiff,
    MarketAnswer,
    MilestoneRadar,
    MoaLandscape,
    SourceSelection,
)
from ..core.sources.openfda import OpenFdaClient
from ..core import grade as grade_mod
from ..core import living as living_mod
from ..core import llm as llm_mod
from ..core import rob as rob_mod
from ..core import search as search_mod
from ..core import validate as validate_mod
from ..core import pipeline as pipeline_mod
from ..core.pipeline import (
    repool_with_decisions,
    repool_with_diversity,
    run_review_collect,
)
from ..core.schema import (
    DiversityDecision,
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
from ..core.sources.europepmc import EuropePmcClient
from ..core.stats import engine as stats_engine
from ..core.stats import sensitivity as sensitivity_mod
from ..core.store import SnapshotStore, make_store

mcp = FastMCP("livemeta")

# --- Dependency seams (overridden in tests to run offline) -------------------

_client: ClinicalTrialsClient | None = None
_epmc_client: EuropePmcClient | None = None
_store: SnapshotStore | None = None


def set_client(client: ClinicalTrialsClient) -> None:
    global _client
    _client = client


def get_client() -> ClinicalTrialsClient:
    global _client
    if _client is None:
        _client = ClinicalTrialsClient()
    return _client


def set_epmc_client(client: EuropePmcClient) -> None:
    global _epmc_client
    _epmc_client = client


def get_epmc_client() -> EuropePmcClient:
    global _epmc_client
    if _epmc_client is None:
        _epmc_client = EuropePmcClient()
    return _epmc_client


_openfda: OpenFdaClient | None = None


def set_openfda(client: OpenFdaClient) -> None:
    global _openfda
    _openfda = client


def get_openfda() -> OpenFdaClient | None:
    """The openFDA approvals client, or None when disabled.

    Disabled for now: the live openFDA lookups were surfacing inaccurate
    approvals, so we default to None to suppress all regulatory-approval
    fetching. A client set via ``set_openfda`` (e.g. in tests) still takes
    precedence; restore ``OpenFdaClient()`` below to re-enable by default. The
    service layer treats a None client as "no approvals" without erroring.
    """
    return _openfda


def set_store(store: SnapshotStore) -> None:
    global _store
    _store = store


def get_store() -> SnapshotStore:
    global _store
    if _store is None:
        _store = make_store()
    return _store


def _discover(pico) -> list[str]:
    """Discover candidate NCT ids for a PICO via the injected CT.gov client."""
    return [c.nct_id for c in search_mod.search_trials(pico, client=get_client())]


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
def extract_effects(trial_id: str, measure: str = "HR") -> TrialExtraction:
    """Extract the primary effect for one trial (per `measure`), with provenance.

    Routes by reference id: an NCT id is read from ClinicalTrials.gov structured
    results; a PMID/PMC id is read from the Europe PMC published record by Claude.
    Dispatches on the effect measure (ratio+CI, 2x2, or mean/SD/n) and flags
    rather than guesses when the effect is absent, incomplete, or low-confidence.
    """
    if trial_id.strip().upper().startswith("NCT"):
        study = get_client().fetch_study(trial_id)
        return extract_mod.extract(study, EffectMeasure(measure))
    doc = get_epmc_client().fetch_study(trial_id)
    return extract_mod.extract_from_text(doc, EffectMeasure(measure))


@mcp.tool()
def search_publications(query: str, max_results: int = 25) -> list[TrialCandidate]:
    """Search Europe PMC for published trials (PMID/PMC), the second data source.

    Complements `search_trials` (ClinicalTrials.gov) for trials whose effect data
    lives in a paper rather than a structured registry result.
    """
    hits = get_epmc_client().search_studies(query, page_size=max_results)
    return [
        TrialCandidate(nct_id=h["id"], title=h.get("title", ""), source="europepmc")
        for h in hits
        if h.get("id")
    ]


@mcp.tool()
def validate(extractions: list[dict]) -> list[ValidationResult]:
    """Run the deterministic validation gate over extracted effects.

    Accepts the extraction objects returned by `extract_effects`. Returns a
    pass/flag verdict per trial; anything flagged must not be pooled.
    """
    parsed = [TrialExtraction.model_validate(e) for e in extractions]
    return validate_mod.validate_extractions(parsed)


@mcp.tool()
def pool(extractions: list[dict], measure: str = "HR") -> PoolResult:
    """Pool validated effects with a random-effects meta-analysis (REML).

    Re-runs the deterministic gate and pools only the trials that pass — the
    model never selects or computes the pooled numbers. Requires at least two
    valid trials.
    """
    parsed = [TrialExtraction.model_validate(e) for e in extractions]
    validations = validate_mod.validate_extractions(parsed)
    passed = {v.study_id for v in validations if v.passed}
    inputs = pipeline_mod._pool_inputs(parsed, passed)
    return stats_engine.pool(inputs, measure=EffectMeasure(measure))


@mcp.tool()
def parse_question(text: str) -> Question:
    """Structure a free-text clinical question into PICO + candidate trials.

    Claude reads and structures the question; ClinicalTrials.gov search fills in
    the candidate trial ids. Every question is parsed live through the same path —
    the GLP-1 MACE demo is not special-cased — so the PICO depends on the model
    being reachable rather than a curated substitute.
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
def confirm_diversity(question_id: str, reason: str | None = None) -> ReviewResult:
    """Lift the homogeneity gate for a withheld review and pool it.

    When a review was withheld because the trials were clinically diverse or
    statistically heterogeneous, a human confirms they are combinable; this
    re-pools the same validated extractions and snapshots the result. The model
    never edits numbers — confirmation only lifts the gate.
    """
    store = get_store()
    latest = store.load_latest(question_id)
    if latest is None:
        raise ValueError(
            f"No existing review for question_id {question_id!r}; run `run_review` first."
        )
    confirmed = repool_with_diversity(latest, DiversityDecision(reason=reason))
    store.save_snapshot(confirmed)
    return confirmed


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
    validations = validate_mod.validate_extractions(latest.extractions)
    passed = {v.study_id for v in validations if v.passed}
    inputs = pipeline_mod._pool_inputs(latest.extractions, passed)
    return sensitivity_mod.leave_one_out(inputs, measure=latest.question.measure)


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
def run_review(question_text: str) -> ReviewResult:
    """Parse a free-text clinical question, run the whole pipeline, snapshot it.

    Claude structures the free text into PICO, the search discovers candidate
    trials, and the deterministic core runs retrieve -> extract -> validate ->
    pool. The result is persisted so `update` has a baseline to diff against.
    Nothing is hardcoded — every question is parsed and discovered live.
    """
    question = llm_mod.parse_question(question_text, search_client=get_client())
    result = run_review_collect(
        question, get_client().fetch_study, search_fn=_discover
    )
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


@mcp.tool()
def check_updates(question_id: str) -> list[TrialCandidate]:
    """Re-search a saved review's PICO and return trials new since the last run.

    The discovery half of the living layer: it re-runs the same PICO search that
    built the review and diffs the hits against the ids already pooled, so what
    comes back is exactly the set a reviewer could feed to `update`. It never
    auto-pools. Shares its core with the REST `check-updates` endpoint via
    `living.check_for_new_trials`.
    """
    return living_mod.check_for_new_trials(get_store(), question_id, get_client())


@mcp.tool()
def map_landscape(condition: str, as_of: str | None = None) -> Landscape:
    """Map the competitive pipeline for a condition, as of an optional date.

    Assets × indications from ClinicalTrials.gov (sponsor, phase, status, dates),
    reconciled over time so `as_of` reconstructs the pipeline at a past point.
    Cells linked to a saved review carry that review's living pooled-evidence
    badge — the competitive skeleton joined to the evidence flesh.
    """
    return ci_service.get_landscape(
        get_store(), condition, as_of=as_of, search_pipeline=get_client().search_pipeline
    )


@mcp.tool()
def track_asset(condition: str, name: str) -> list[DevelopmentEvent]:
    """Return one asset's dated development timeline within a condition landscape."""
    ci_service.get_landscape(
        get_store(), condition, search_pipeline=get_client().search_pipeline
    )  # ensure the landscape is seeded before reading the timeline
    return ci_service.asset_timeline(get_store(), condition, name)


@mcp.tool()
def company_pipeline(name: str, as_of: str | None = None) -> CompanyPipeline:
    """Map a pharma company's entire pipeline across every indication and phase.

    The cross-condition companion to `map_landscape`: pulls every trial the
    company leads (CT.gov lead-sponsor search), so the same asset can appear in
    several indications, reconciled over time (`as_of` reconstructs a past
    pipeline), and joined to the company's openFDA approvals. Readouts and
    evidence badges come through on the cells exactly as on the condition board.
    """
    return ci_service.company_pipeline(
        get_store(),
        name,
        as_of=as_of,
        search=get_client().search_by_sponsor,
        openfda=get_openfda(),
    )


@mcp.tool()
def ingest_announcement(
    condition: str, text: str, source_label: str
) -> list[DevelopmentEvent]:
    """Read a free-text corporate announcement/filing into development events.

    Claude structures what the document states (each event with its source
    snippet); low-confidence or not-found milestones are dropped, and with no key
    configured nothing is returned — the tool abstains rather than inventing a
    stage. Persisted so they appear on the landscape.
    """
    return ci_service.ingest_to_landscape(get_store(), condition, text, source_label)


@mcp.tool()
def asset_dossier(name: str, sources: str | None = None) -> AssetDossier:
    """Deep competitive dossier for one drug: every trial (phase, status,
    enrolment, countries, readouts), pipeline events, sub-indications, openFDA
    approvals, and the living pooled evidence. `sources` (comma list) selects the
    data sources; default is the structured trio (ctgov, pubmed, openfda)."""
    return ci_service.asset_dossier(
        get_store(),
        name,
        search=get_client().search_by_intervention,
        openfda=get_openfda(),
        selection=SourceSelection.from_param(sources),
    )


@mcp.tool()
def indication_map(name: str, sources: str | None = None) -> IndicationMap:
    """Break an indication into its sub-populations (e.g. obesity + established
    CVD, obesity in adults >=65), each with the assets, stage distribution,
    geography, and evidence targeting it."""
    return ci_service.indication_map(
        get_store(),
        name,
        search=get_client().search_by_condition,
        selection=SourceSelection.from_param(sources),
    )


@mcp.tool()
def landscape_changes(
    condition: str, since: str | None = None, until: str | None = None
) -> LandscapeDiff:
    """What moved in a condition's competitive landscape between two dates.

    The market-intelligence analogue of `update`: reconstructs the landscape at
    `since` and `until` (a pure filter over the same dated events) and reports the
    deltas — stage advances, new programs, trial readouts, living-evidence moves
    (conclusion changes, not bare numbers), and newly-opened source conflicts —
    newest first, each traced to the events or review versions that produced it.
    """
    return ci_changefeed.landscape_changes(
        get_store(), condition, since=since, until=until,
        search_pipeline=get_client().search_pipeline,
    )


@mcp.tool()
def milestone_radar(
    condition: str, horizon_months: int = 18, as_of: str | None = None
) -> MilestoneRadar:
    """Upcoming trial readouts for a condition, bucketed by quarter — the one
    forward-looking lens. Surfaces trials whose primary completion is in the future
    (relative to `as_of`/today), within the horizon, and not yet reported."""
    return ci_radar.milestone_radar(
        get_store(), condition, search=get_client().search_pipeline,
        horizon_months=horizon_months, as_of=as_of,
    )


@mcp.tool()
def moa_landscape(condition: str) -> MoaLandscape:
    """Group a condition's assets by mechanism of action, with class-level evidence.

    Mechanism is inferred (Claude when a key is set, else the WHO INN-stem
    convention) and cached per asset; assets that can't be classed confidently
    group under 'unclassified' — never a fabricated class."""
    return ci_moa.moa_landscape(
        get_store(), condition, search=get_client().search_pipeline
    )


@mcp.tool()
def compare_assets(assets: str, indication: str | None = None) -> AssetComparison:
    """Side-by-side profile of two or more assets (comma-separated names).

    Compares OPERATIONAL facts (phase, pivotal trial, enrollment, geography, next
    readout). It deliberately does NOT rank the pooled efficacy: two estimates from
    separate meta-analyses are an unanchored indirect comparison, so each asset's
    evidence is shown in its own context and a comparability check flags them as
    not directly comparable. Abstaining from the verdict is the trust story."""
    names = [a.strip() for a in assets.split(",") if a.strip()]
    return ci_compare.compare_assets(
        get_store(), names, indication,
        search=get_client().search_by_intervention, openfda=get_openfda(),
    )


@mcp.tool()
def market_ask(text: str) -> MarketAnswer:
    """Answer a plain-language market-intelligence question by routing it to the
    right tool and returning that tool's typed payload plus a grounded narrative.

    Claude picks the tool (landscape, changes, compare, radar, moa, dossier,
    company, indication) and extracts params; deterministic code produces every
    figure. The unifying front door over the whole market-intelligence surface."""
    client = get_client()
    deps = MarketDeps(
        search_condition=client.search_pipeline,
        search_asset=client.search_by_intervention,
        search_sponsor=client.search_by_sponsor,
        search_indication=client.search_by_condition,
        openfda=get_openfda(),
        llm_client=None,  # ask/moa resolve the LLM from ANTHROPIC_API_KEY, else deterministic
    )
    return ci_ask.answer(get_store(), text, deps=deps)


def main() -> None:
    """Console-script entry point: serve the tools over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
