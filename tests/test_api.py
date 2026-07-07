"""FastAPI surface — REST run endpoint and the WebSocket event stream.

Driven offline: the CT.gov fetch dependency is overridden with recorded fixtures.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from livemeta.api.app import app, get_fetch_study

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_fetch():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return fetch


app.dependency_overrides[get_fetch_study] = _fixture_fetch
client = TestClient(app)


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


def test_ws_streams_pipeline_events():
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
