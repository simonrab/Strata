"""FastAPI adapter — REST + WebSocket over the shared pipeline core.

The CT.gov fetch, the snapshot store, and the question parser are all injected
dependencies so they can be overridden (tests, or a future cached source). The
WebSocket streams PipelineEvents as they are produced, running the blocking
pipeline in a worker thread to keep the event loop free.
"""

from __future__ import annotations

import sys

# Load local .env (DATABASE_URL, ANTHROPIC_API_KEY) so the dev server and the
# preview pick up Supabase without a wrapper script. Skipped under pytest, which
# configures its stores explicitly and must stay network-free.
if "pytest" not in sys.modules:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

import anyio
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core import demo, living, llm, pipeline, rob as rob_mod
from ..core.ci import service as ci_service
from ..core.ci.schema import (
    AssetDossier,
    DevelopmentEvent,
    IndicationMap,
    Landscape,
    SourceSelection,
)
from ..core.sources.openfda import OpenFdaClient
from ..core.diff import diff_reviews, status_from_diff
from ..core.schema import (
    DiversityDecision,
    EligibilityDecision,
    Question,
    ReviewDecision,
    ReviewDiff,
    ReviewResult,
    ReviewSummary,
    RobDecision,
    SnapshotMeta,
    TrialCandidate,
)
from ..core.sources.clinicaltrials import ClinicalTrialsClient
from ..core.sources.europepmc import EuropePmcClient
from ..core.sources.router import SourceRouter
from ..core.store import SnapshotStore, make_store

app = FastAPI(title="LiveMeta", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_fetch_study():
    """Injectable trial fetch (overridden in tests).

    Defaults to the multi-source router so a review can pull NCT ids from
    ClinicalTrials.gov and PMID/PMC ids from Europe PMC.
    """
    return SourceRouter().fetch


def get_store() -> SnapshotStore:
    """Injectable snapshot store (overridden in tests to a tmp dir). In production
    `make_store()` returns the Postgres backend when DATABASE_URL is set."""
    return make_store()


def get_parse():
    """Injectable free-text -> Question parser (overridden in tests).

    Discovery spans both sources: ClinicalTrials.gov (structured results) and
    Europe PMC (published literature), so a real question's candidate set is a
    genuinely systematic, multi-source search rather than a single registry.
    """

    def parse(text: str) -> Question:
        return llm.parse_question(
            text,
            search_client=ClinicalTrialsClient(),
            epmc_client=EuropePmcClient(),
        )

    return parse


def get_search_client():
    """Injectable CT.gov search client for the living re-search (overridden in tests)."""
    return ClinicalTrialsClient()


def get_ci_search():
    """Injectable CT.gov pipeline search for the competitive landscape.

    Returns the wide-fields search that keeps sponsor/phase/status/interventions
    (overridden in tests with canned studies so the landscape is network-free)."""
    return ClinicalTrialsClient().search_pipeline


def get_ci_asset_search():
    """Injectable CT.gov search by intervention (a drug's trials) for the dossier."""
    return ClinicalTrialsClient().search_by_intervention


def get_ci_indication_search():
    """Injectable CT.gov search by condition (an indication's trials) for the map."""
    return ClinicalTrialsClient().search_by_condition


def get_openfda():
    """Injectable openFDA approvals client (overridden in tests)."""
    return OpenFdaClient()


class ParseRequest(BaseModel):
    text: str


class DecisionRequest(BaseModel):
    study_id: str
    decision: str  # "confirmed" | "flagged"
    reason: str | None = None


class RobDecisionRequest(BaseModel):
    study_id: str
    domain_key: str
    reason: str | None = None


class UpdateRequest(BaseModel):
    new_trial_id: str


class DiversityDecisionRequest(BaseModel):
    reason: str | None = None


class ScreeningDecisionRequest(BaseModel):
    study_id: str
    decision: str  # "included" | "excluded"
    reason: str | None = None


class IngestRequest(BaseModel):
    condition: str
    text: str
    source_label: str


class LinkRequest(BaseModel):
    condition: str
    asset_name: str
    indication: str
    question_id: str


def _summary(result: ReviewResult, versions: int, status: str) -> ReviewSummary:
    pool = result.pool
    return ReviewSummary(
        question_id=result.question.id,
        text=result.question.text,
        versions=versions,
        k=pool.k if pool else 0,
        estimate=pool.estimate if pool else None,
        ci_low=pool.ci_low if pool else None,
        ci_high=pool.ci_high if pool else None,
        measure=result.question.measure.value,
        status=status,
    )


@app.get("/api/demo", response_model=Question)
def demo_question() -> Question:
    return demo.GLP1_MACE_QUESTION


@app.post("/api/parse", response_model=Question)
def parse_question(req: ParseRequest, parse=Depends(get_parse)) -> Question:
    return parse(req.text)


@app.post("/api/reviews/run", response_model=ReviewResult)
def run_review(
    question: Question | None = None,
    fetch=Depends(get_fetch_study),
    store: SnapshotStore = Depends(get_store),
) -> ReviewResult:
    q = question or demo.GLP1_MACE_QUESTION
    result = pipeline.run_review_collect(q, fetch)
    store.save_snapshot(result)
    return result


def _dashboard_status(store: SnapshotStore, qid: str, versions: list[int], latest: ReviewResult) -> str:
    """Compare the latest snapshot to its predecessor (no re-pool) for the pill."""
    if len(versions) < 2:
        return "unchanged"
    previous = store.load_version(qid, versions[-2])
    if previous is None:
        return "unchanged"
    diff = diff_reviews(
        previous, latest, previous_version=versions[-2], current_version=versions[-1]
    )
    return status_from_diff(diff)


@app.post("/api/reviews/demo/seed", response_model=ReviewResult)
def seed_demo(
    fetch=Depends(get_fetch_study), store: SnapshotStore = Depends(get_store)
) -> ReviewResult:
    """Seed the living-layer demo: the 7-trial GLP-1 baseline before AMPLITUDE-O.

    Idempotent — returns the existing baseline if one is already saved, so the
    demo can be reset by clearing the store rather than by stacking versions.
    """
    existing = store.load_latest(demo.GLP1_MACE_QUESTION.id)
    if existing is not None:
        return existing
    return demo.seed_baseline(store, fetch)


@app.get("/api/reviews", response_model=list[ReviewSummary])
def list_reviews(store: SnapshotStore = Depends(get_store)) -> list[ReviewSummary]:
    summaries = []
    for qid in store.list_questions():
        latest = store.load_latest(qid)
        if latest is None:
            continue
        versions = store.list_versions(qid)
        status = _dashboard_status(store, qid, versions, latest)
        summaries.append(_summary(latest, len(versions), status=status))
    return summaries


@app.get("/api/reviews/{question_id}", response_model=ReviewResult)
def get_review(
    question_id: str, store: SnapshotStore = Depends(get_store)
) -> ReviewResult:
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")
    return latest


@app.post("/api/reviews/{question_id}/update", response_model=ReviewDiff)
def update_review(
    question_id: str,
    req: UpdateRequest,
    fetch=Depends(get_fetch_study),
    store: SnapshotStore = Depends(get_store),
) -> ReviewDiff:
    """The living layer over HTTP: add a trial, re-run, and diff against the
    previous version. Shares its core with the MCP `update` tool."""
    try:
        return living.apply_update(store, question_id, req.new_trial_id, fetch)
    except ValueError:
        raise HTTPException(status_code=404, detail="No such review.")


@app.post("/api/reviews/{question_id}/check-updates", response_model=list[TrialCandidate])
def check_updates(
    question_id: str,
    search_client=Depends(get_search_client),
    store: SnapshotStore = Depends(get_store),
) -> list[TrialCandidate]:
    """Make the living claim real: re-search the saved question's PICO and return
    the trials that are genuinely new since the last run. Discovery only — the
    reviewer decides whether to inject one via the update endpoint. Shares its
    core with the MCP `check_updates` tool."""
    try:
        return living.check_for_new_trials(store, question_id, search_client)
    except ValueError:
        raise HTTPException(status_code=404, detail="No such review.")


@app.get("/api/reviews/{question_id}/history", response_model=list[SnapshotMeta])
def review_history(
    question_id: str, store: SnapshotStore = Depends(get_store)
) -> list[SnapshotMeta]:
    """The version timeline for the audit trail (empty when the review is unknown)."""
    return store.list_snapshots(question_id)


@app.get("/api/reviews/{question_id}/versions/{version}", response_model=ReviewResult)
def review_version(
    question_id: str, version: int, store: SnapshotStore = Depends(get_store)
) -> ReviewResult:
    """One historical snapshot, read-only, for the audit-trail detail view."""
    result = store.load_version(question_id, version)
    if result is None:
        raise HTTPException(status_code=404, detail="No such snapshot.")
    return result


@app.post("/api/reviews/{question_id}/decision", response_model=ReviewResult)
def record_decision(
    question_id: str,
    req: DecisionRequest,
    store: SnapshotStore = Depends(get_store),
) -> ReviewResult:
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")

    store.save_decision(
        question_id,
        ReviewDecision(
            study_id=req.study_id, decision=req.decision, reason=req.reason
        ),
    )
    repooled = pipeline.repool_with_decisions(
        latest, store.load_decisions(question_id)
    )
    store.save_snapshot(repooled)
    return repooled


@app.post("/api/reviews/{question_id}/diversity/decision", response_model=ReviewResult)
def confirm_diversity(
    question_id: str,
    req: DiversityDecisionRequest,
    store: SnapshotStore = Depends(get_store),
) -> ReviewResult:
    """Lift the homogeneity gate: a reviewer confirms clinically diverse trials
    may be pooled, and the withheld review is re-pooled and snapshotted."""
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")
    confirmed = pipeline.repool_with_diversity(
        latest, DiversityDecision(reason=req.reason)
    )
    store.save_snapshot(confirmed)
    return confirmed


@app.post("/api/reviews/{question_id}/rob/decision", response_model=ReviewResult)
def record_rob_decision(
    question_id: str,
    req: RobDecisionRequest,
    store: SnapshotStore = Depends(get_store),
) -> ReviewResult:
    """Persist a human "Verify" on one RoB 2 domain and snapshot the sign-off."""
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")

    store.save_rob_decision(
        question_id,
        RobDecision(
            study_id=req.study_id, domain_key=req.domain_key, reason=req.reason
        ),
    )
    decisions = store.load_rob_decisions(question_id)
    latest.rob = [rob_mod.apply_rob_decisions(a, decisions) for a in latest.rob]
    store.save_snapshot(latest)
    return latest


@app.post("/api/reviews/{question_id}/screening/decision", response_model=ReviewResult)
def record_screening_decision(
    question_id: str,
    req: ScreeningDecisionRequest,
    fetch=Depends(get_fetch_study),
    store: SnapshotStore = Depends(get_store),
) -> ReviewResult:
    """Record a reviewer's include/exclude sign-off on one trial's eligibility.

    Confirming keeps Claude's call (with `decision` equal to it); overriding flips
    it. Because a screened-out trial is never extracted, the decision is applied by
    *re-running* the review with every stored eligibility override replayed — so
    flipping a trial back in re-fetches and re-pools it. Human extraction and RoB
    sign-offs are re-applied afterward so the audit trail is preserved.
    """
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")

    store.save_screening_decision(
        question_id,
        EligibilityDecision(
            study_id=req.study_id,
            decision=req.decision,
            reason=req.reason or "Reviewer sign-off.",
            by_claude=False,
            confirmed=True,
        ),
    )
    overrides = {d.study_id: d for d in store.load_screening_decisions(question_id)}
    rerun = pipeline.run_review_collect(
        latest.question, fetch, screening_overrides=overrides
    )
    review_decisions = store.load_decisions(question_id)
    if review_decisions:
        rerun = pipeline.repool_with_decisions(rerun, review_decisions)
    rob_decisions = store.load_rob_decisions(question_id)
    if rob_decisions:
        rerun.rob = [rob_mod.apply_rob_decisions(a, rob_decisions) for a in rerun.rob]
    store.save_snapshot(rerun)
    return rerun


# --- Competitive-intelligence landscape -------------------------------------


@app.get("/api/landscape", response_model=Landscape)
def get_landscape(
    condition: str,
    as_of: str | None = None,
    refresh: bool = False,
    store: SnapshotStore = Depends(get_store),
    search=Depends(get_ci_search),
) -> Landscape:
    """The competitive matrix for a condition, reconstructed as of `as_of`.

    Assets × indications, cells colored by development stage, each carrying the
    living pooled-evidence badge when linked to a saved review.

    `refresh=true` drops the condition's cached CT.gov events and re-pulls them
    from the live (condition-scoped) search — use it to clean a stale cache.
    """
    return ci_service.get_landscape(
        store, condition, as_of=as_of, search_pipeline=search, refresh=refresh
    )


@app.get("/api/landscape/asset/{name}", response_model=list[DevelopmentEvent])
def get_asset_timeline(
    name: str, condition: str, store: SnapshotStore = Depends(get_store)
) -> list[DevelopmentEvent]:
    """One asset's dated development history for the drill-in view."""
    return ci_service.asset_timeline(store, condition, name)


@app.post("/api/landscape/ingest", response_model=Landscape)
def ingest_landscape(
    req: IngestRequest,
    store: SnapshotStore = Depends(get_store),
) -> Landscape:
    """Read a free-text announcement/filing into events, then re-assemble.

    The model is resolved from ANTHROPIC_API_KEY inside the service; with no key
    it returns no events (the tool abstains rather than invents a pipeline)."""
    ci_service.ingest_to_landscape(store, req.condition, req.text, req.source_label)
    return ci_service.get_landscape(store, req.condition)


@app.post("/api/landscape/link", response_model=Landscape)
def link_landscape(
    req: LinkRequest,
    store: SnapshotStore = Depends(get_store),
) -> Landscape:
    """Link an asset×indication cell to a saved review so its evidence badge shows."""
    ci_service.link_review(
        store, req.condition, req.asset_name, req.indication, req.question_id
    )
    return ci_service.get_landscape(store, req.condition)


@app.get("/api/asset/{name}", response_model=AssetDossier)
def asset_dossier(
    name: str,
    sources: str | None = None,
    store: SnapshotStore = Depends(get_store),
    search=Depends(get_ci_asset_search),
    openfda=Depends(get_openfda),
) -> AssetDossier:
    """Deep dossier for one drug: every trial, geography, readouts, events,
    sub-indications, approvals, and the living pooled evidence. `sources` selects
    which data sources are used (default: the structured trio)."""
    selection = SourceSelection.from_param(sources)
    return ci_service.asset_dossier(
        store, name, search=search, openfda=openfda, selection=selection
    )


@app.get("/api/indication/{name}", response_model=IndicationMap)
def indication_map(
    name: str,
    sources: str | None = None,
    store: SnapshotStore = Depends(get_store),
    search=Depends(get_ci_indication_search),
) -> IndicationMap:
    """An indication broken into its sub-populations, each with its assets,
    stage distribution, geography, and evidence."""
    selection = SourceSelection.from_param(sources)
    return ci_service.indication_map(store, name, search=search, selection=selection)


@app.websocket("/ws/review")
async def ws_review(
    websocket: WebSocket,
    fetch=Depends(get_fetch_study),
    store: SnapshotStore = Depends(get_store),
) -> None:
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        question = _question_from_payload(payload)
        gen = pipeline.run_review(question, fetch)

        final: ReviewResult | None = None
        while True:
            event = await anyio.to_thread.run_sync(lambda: next(gen, None))
            if event is None:
                break
            if event.stage == "done" and event.data is not None:
                final = ReviewResult.model_validate(event.data)
            await websocket.send_json(event.model_dump())

        if final is not None:
            store.save_snapshot(final)
        await websocket.close()
    except WebSocketDisconnect:
        return


def _question_from_payload(payload: dict) -> Question:
    """A WS client either kicks off the demo or supplies a parsed Question."""
    if payload.get("question"):
        return Question.model_validate(payload["question"])
    return demo.GLP1_MACE_QUESTION


# --- Serve the built web UI (single-origin deploy) ---------------------------
#
# When a built SPA is present (LIVEMETA_WEB_DIST, or ./static_web next to the
# repo root), the backend serves it too, so one Railway URL is the whole app —
# no separate frontend host, no CORS. Client-side routes (/landscape, /reviews/…)
# fall back to index.html. Defined last so every /api and /ws route wins first.
import os as _os  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
_WEB_DIST = _os.environ.get("LIVEMETA_WEB_DIST", _os.path.join(_REPO_ROOT, "static_web"))

if _os.path.isdir(_WEB_DIST):
    _ASSETS = _os.path.join(_WEB_DIST, "assets")
    if _os.path.isdir(_ASSETS):
        app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa(full_path: str):
        """Serve a real static file if it exists, else the SPA entrypoint."""
        candidate = _os.path.join(_WEB_DIST, full_path)
        if full_path and _os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(_os.path.join(_WEB_DIST, "index.html"))
