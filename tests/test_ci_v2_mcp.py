"""v2 MCP tools: asset_dossier + indication_map, driven offline."""

from livemeta.core.store import SnapshotStore
from livemeta.mcp import server
from tests.test_ci_trialdetail import _study_detail


class _DetailClient:
    def __init__(self, studies):
        self._studies = studies

    def fetch_study(self, nct_id):
        return {}

    def search_studies(self, query, page_size=20):
        return []

    def search_by_intervention(self, name, page_size=1000):
        return self._studies

    def search_by_condition(self, name, page_size=1000):
        return self._studies


class _StubOpenFda:
    def approvals_for(self, drug, limit=20):
        from livemeta.core.ci.schema import RegulatoryApproval

        return [RegulatoryApproval(drug=drug, application_number="NDA1")]


def _setup(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    studies = [
        _study_detail(nct="NCT1", has_results=True),
        _study_detail(nct="NCT2", status="RECRUITING", has_results=False, results_posted=None),
    ]
    server.set_client(_DetailClient(studies))
    server.set_store(SnapshotStore(tmp_path))
    server.set_openfda(_StubOpenFda())


def test_asset_dossier_tool(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    d = server.asset_dossier("Semaglutide")
    assert d.asset.name == "Semaglutide"
    assert len(d.trials) == 2
    assert len(d.readouts) == 1
    assert [a.application_number for a in d.approvals] == ["NDA1"]


def test_asset_dossier_tool_source_toggle(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    d = server.asset_dossier("Semaglutide", sources="ctgov")  # openFDA off
    assert d.approvals == []


def test_indication_map_tool(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    m = server.indication_map("Obesity")
    assert m.indication == "Obesity"
    assert m.nodes and m.nodes[0].trial_count == 2
