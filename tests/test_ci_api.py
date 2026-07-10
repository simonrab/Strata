"""REST surface for the competitive landscape (network-free).

The CT.gov pipeline search is overridden with canned studies and the store with
a tmp SQLite db, so the endpoints exercise the real service end to end offline.
"""

import pytest
from fastapi.testclient import TestClient

from livemeta.api.app import app, get_ci_search, get_store
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


@pytest.fixture
def client(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Type 2 Diabetes",),
               interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT2", conditions=("Type 2 Diabetes",), phases=("PHASE2",),
               status="RECRUITING", primary_completion=None,
               interventions=(("DRUG", "Tirzepatide"),)),
    ]
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_ci_search] = lambda: (lambda condition: studies)
    yield TestClient(app)
    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(get_ci_search, None)


def test_landscape_endpoint_returns_matrix(client):
    r = client.get("/api/landscape", params={"condition": "Type 2 Diabetes"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["assets"]) == {"Semaglutide", "Tirzepatide"}
    assert body["indications"] == ["Type 2 Diabetes"]
    assert len(body["cells"]) == 2


def test_landscape_refresh_reseeds_from_a_clean_search(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # The live search swaps its result to simulate the query.cond fix landing
    # between the stale first seed and the refresh.
    state = {
        "studies": [_study(nct="NCT9", conditions=("Obesity",),
                           interventions=(("DRUG", "Karolinska Cocktail"),))]
    }
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_ci_search] = lambda: (lambda cond: state["studies"])
    try:
        c = TestClient(app)
        seeded = c.get("/api/landscape", params={"condition": "Obesity"}).json()
        assert "Karolinska Cocktail" in seeded["assets"]

        state["studies"] = [_study(nct="NCT10", conditions=("Obesity",),
                                   interventions=(("DRUG", "Semaglutide"),))]
        # Without refresh, the stale cache is served.
        cached = c.get("/api/landscape", params={"condition": "Obesity"}).json()
        assert "Karolinska Cocktail" in cached["assets"]

        refreshed = c.get(
            "/api/landscape", params={"condition": "Obesity", "refresh": "true"}
        ).json()
        assert "Semaglutide" in refreshed["assets"]
        assert "Karolinska Cocktail" not in refreshed["assets"]
    finally:
        app.dependency_overrides.pop(get_store, None)
        app.dependency_overrides.pop(get_ci_search, None)


def test_landscape_as_of_filters_future_events(client):
    # Seed first, then ask for a date before either trial started.
    client.get("/api/landscape", params={"condition": "Type 2 Diabetes"})
    r = client.get(
        "/api/landscape",
        params={"condition": "Type 2 Diabetes", "as_of": "2000-01-01"},
    )
    assert r.json()["cells"] == []


def test_asset_timeline_endpoint(client):
    client.get("/api/landscape", params={"condition": "Type 2 Diabetes"})
    r = client.get(
        "/api/landscape/asset/Semaglutide", params={"condition": "Type 2 Diabetes"}
    )
    assert r.status_code == 200
    events = r.json()
    assert events and all(e["asset_name"] == "Semaglutide" for e in events)


def test_link_endpoint_attaches_question_id(client):
    client.get("/api/landscape", params={"condition": "Type 2 Diabetes"})
    r = client.post(
        "/api/landscape/link",
        json={
            "condition": "Type 2 Diabetes",
            "asset_name": "Semaglutide",
            "indication": "Type 2 Diabetes",
            "question_id": "glp1-mace",
        },
    )
    assert r.status_code == 200
    cell = next(c for c in r.json()["cells"] if c["asset_name"] == "Semaglutide")
    assert cell["question_id"] == "glp1-mace"


def test_ingest_endpoint_without_key_is_a_noop(client, monkeypatch):
    # No ANTHROPIC_API_KEY -> the tool abstains; the matrix is unchanged, not invented.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client.get("/api/landscape", params={"condition": "Type 2 Diabetes"})
    r = client.post(
        "/api/landscape/ingest",
        json={
            "condition": "Type 2 Diabetes",
            "text": "Some company announces Phase 3 start.",
            "source_label": "PR:x",
        },
    )
    assert r.status_code == 200
    assert set(r.json()["assets"]) == {"Semaglutide", "Tirzepatide"}
