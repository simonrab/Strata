"""FastAPI adapter — REST + WebSocket over the shared pipeline core.

The CT.gov fetch, the snapshot store, and the question parser are all injected
dependencies so they can be overridden (tests, or a future cached source). The
WebSocket streams PipelineEvents as they are produced, running the blocking
pipeline in a worker thread to keep the event loop free.
"""

from __future__ import annotations

import anyio
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core import demo, llm, pipeline
from ..core.schema import (
    Question,
    ReviewDecision,
    ReviewResult,
    ReviewSummary,
)
from ..core.sources.clinicaltrials import ClinicalTrialsClient
from ..core.store import SnapshotStore

app = FastAPI(title="LiveMeta", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_fetch_study():
    """Injectable ClinicalTrials.gov fetch (overridden in tests)."""
    return ClinicalTrialsClient().fetch_study


def get_store() -> SnapshotStore:
    """Injectable snapshot store (overridden in tests to a tmp dir)."""
    return SnapshotStore()


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


@app.get("/api/reviews", response_model=list[ReviewSummary])
def list_reviews(store: SnapshotStore = Depends(get_store)) -> list[ReviewSummary]:
    summaries = []
    for qid in store.list_questions():
        latest = store.load_latest(qid)
        if latest is None:
            continue
        versions = len(store.list_versions(qid))
        summaries.append(_summary(latest, versions, status="unchanged"))
    return summaries


@app.get("/api/reviews/{question_id}", response_model=ReviewResult)
def get_review(
    question_id: str, store: SnapshotStore = Depends(get_store)
) -> ReviewResult:
    latest = store.load_latest(question_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No such review.")
    return latest


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
