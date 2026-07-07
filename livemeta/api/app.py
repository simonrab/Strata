"""FastAPI adapter — REST + WebSocket over the shared pipeline core.

The CT.gov fetch is a dependency so it can be overridden (tests, or a future
cached source). The WebSocket streams PipelineEvents as they are produced,
running the blocking pipeline in a worker thread to keep the event loop free.
"""

from __future__ import annotations

import anyio
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..core import demo, pipeline
from ..core.schema import Question, ReviewResult
from ..core.sources.clinicaltrials import ClinicalTrialsClient

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


@app.get("/api/demo", response_model=Question)
def demo_question() -> Question:
    return demo.GLP1_MACE_QUESTION


@app.post("/api/reviews/run", response_model=ReviewResult)
def run_review(question: Question | None = None, fetch=Depends(get_fetch_study)) -> ReviewResult:
    q = question or demo.GLP1_MACE_QUESTION
    return pipeline.run_review_collect(q, fetch)


@app.websocket("/ws/review")
async def ws_review(websocket: WebSocket, fetch=Depends(get_fetch_study)) -> None:
    await websocket.accept()
    try:
        await websocket.receive_json()  # client kicks off; Slice 1 = demo question
        question = demo.GLP1_MACE_QUESTION
        gen = pipeline.run_review(question, fetch)

        while True:
            event = await anyio.to_thread.run_sync(lambda: next(gen, None))
            if event is None:
                break
            await websocket.send_json(event.model_dump())
        await websocket.close()
    except WebSocketDisconnect:
        return
