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
from ..core.diff import diff_reviews, status_from_diff
from ..core.schema import (
    DiversityDecision,
    Question,
    ReviewDecision,
    ReviewDiff,
    ReviewResult,
    ReviewSummary,
    RobDecision,
    SnapshotMeta,
)
from ..core.sources.clinicaltrials import ClinicalTrialsClient
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
    """Injectable free-text -> Question parser (overridden in tests)."""

    def parse(text: str) -> Question:
        return llm.parse_question(text, search_client=ClinicalTrialsClient())

    return parse


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
