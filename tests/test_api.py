"""FastAPI surface — REST run endpoint and the WebSocket event stream.

Driven offline: the CT.gov fetch dependency is overridden with recorded fixtures.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from livemeta.api.app import app, get_fetch_study, get_parse, get_store
from livemeta.core import demo
from livemeta.core.schema import PICO, Question
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_fetch():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return fetch


def _stub_parse():
    def parse(text: str) -> Question:
        return Question(
            id="q-novel",
            text=text,
            pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
            trial_ids=["NCT00000001"],
        )

    return parse


app.dependency_overrides[get_fetch_study] = _fixture_fetch
client = TestClient(app)


@pytest.fixture()
def store(tmp_path):
    """Isolated per-test snapshot store."""
    s = SnapshotStore(tmp_path)
    app.dependency_overrides[get_store] = lambda: s
    yield s
    app.dependency_overrides.pop(get_store, None)


def test_demo_question_endpoint():
    r = client.get("/api/demo")
    assert r.status_code == 200
    assert r.json()["id"] == "glp1-mace"


def test_run_endpoint_returns_pooled_result():
    r = client.post("/api/reviews/run", json=None)
    assert r.status_code == 200
    body = r.json()
    assert round(body["pool"]["estimate"], 2) == 0.86
    assert len(body["extractions"]) == 8
    assert body["pool"]["ci_method"] == "hksj"


def test_ws_streams_pipeline_events(store):
    with client.websocket_connect("/ws/review") as ws:
        ws.send_json({"mode": "demo"})
        stages = []
        while True:
            ev = ws.receive_json()
            stages.append(ev["stage"])
            if ev["stage"] == "done":
                assert "reduced" in ev["message"].lower()
                break
    assert stages[0] == "parse"
    assert "pool" in stages
    assert stages.count("extract") == 8
    # A completed run is persisted so it appears on the dashboard.
    assert store.load_latest("glp1-mace") is not None


def test_parse_endpoint_returns_a_question():
    app.dependency_overrides[get_parse] = _stub_parse
    try:
        r = client.post("/api/parse", json={"text": "novel question?"})
    finally:
        app.dependency_overrides.pop(get_parse, None)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q-novel"
    assert body["trial_ids"] == ["NCT00000001"]


def _demo_review():
    from livemeta.core.pipeline import run_review_collect

    return run_review_collect(demo.GLP1_MACE_QUESTION, _fixture_fetch())


def test_list_reviews_reflects_saved_snapshots(store):
    store.save_snapshot(_demo_review())
    r = client.get("/api/reviews")
    assert r.status_code == 200
    rows = r.json()
    ids = [row["question_id"] for row in rows]
    assert "glp1-mace" in ids
    row = next(row for row in rows if row["question_id"] == "glp1-mace")
    assert round(row["estimate"], 2) == 0.86
    assert row["k"] == 8


def test_get_review_returns_latest_and_404s_when_missing(store):
    store.save_snapshot(_demo_review())
    r = client.get("/api/reviews/glp1-mace")
    assert r.status_code == 200
    assert len(r.json()["extractions"]) == 8

    assert client.get("/api/reviews/does-not-exist").status_code == 404


def test_decision_endpoint_flags_trial_and_repools(store):
    review = _demo_review()
    store.save_snapshot(review)
    target = review.extractions[0].study_id

    r = client.post(
        "/api/reviews/glp1-mace/decision",
        json={"study_id": target, "decision": "flagged", "reason": "unclear arm"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pool"]["k"] == 7
    pooled_ids = {s["study_id"] for s in body["pool"]["studies"]}
    assert target not in pooled_ids
    # Decision persisted + a new snapshot version created (the audit trail).
    assert any(d.study_id == target for d in store.load_decisions("glp1-mace"))
    assert store.list_versions("glp1-mace") == [1, 2]
