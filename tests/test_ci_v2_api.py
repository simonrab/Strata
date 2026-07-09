"""v2 REST surface: asset dossier + indication map, network-free.

CT.gov detail search and openFDA are overridden with canned data; the LLM key is
removed so sub-population extraction degrades to the base indication offline.
"""

import pytest
from fastapi.testclient import TestClient

from livemeta.api.app import (
    app,
    get_ci_asset_search,
    get_ci_indication_search,
    get_openfda,
    get_store,
)
from livemeta.core.store import SnapshotStore
from tests.test_ci_trialdetail import _study_detail


class _StubOpenFda:
    def __init__(self, approvals):
        self._approvals = approvals

    def approvals_for(self, drug, limit=20):
        return list(self._approvals)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study_detail(nct="NCT1", countries=("United States", "Germany"), has_results=True),
        _study_detail(nct="NCT2", countries=("United States",), status="RECRUITING",
                      has_results=False, results_posted=None, primary_completion=None),
    ]
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_ci_asset_search] = lambda: (lambda name: studies)
    app.dependency_overrides[get_ci_indication_search] = lambda: (lambda cond: studies)
    from livemeta.core.ci.schema import RegulatoryApproval
    app.dependency_overrides[get_openfda] = lambda: _StubOpenFda(
        [RegulatoryApproval(drug="Semaglutide", application_number="NDA1", brand_names=["OZEMPIC"])]
    )
    yield TestClient(app)
    for dep in (get_store, get_ci_asset_search, get_ci_indication_search, get_openfda):
        app.dependency_overrides.pop(dep, None)


def test_asset_dossier_endpoint(client):
    r = client.get("/api/asset/Semaglutide")
    assert r.status_code == 200
    body = r.json()
    assert len(body["trials"]) == 2
    assert len(body["readouts"]) == 1
    countries = {c["country"]: c["trials"] for c in body["countries"]}
    assert countries["United States"] == 2 and "Germany" in countries
    assert [a["application_number"] for a in body["approvals"]] == ["NDA1"]


def test_asset_dossier_respects_source_toggle(client):
    # openFDA off -> no approvals
    r = client.get("/api/asset/Semaglutide", params={"sources": "ctgov,pubmed"})
    assert r.json()["approvals"] == []


def test_indication_map_endpoint(client):
    r = client.get("/api/indication/Obesity")
    assert r.status_code == 200
    body = r.json()
    assert body["indication"] == "Obesity"
    # keyless -> sub-populations fall back to the base indication (one node)
    assert len(body["nodes"]) == 1
    node = body["nodes"][0]
    assert node["trial_count"] == 2
    assert "Semaglutide" in node["assets"]
