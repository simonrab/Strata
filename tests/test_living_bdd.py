"""Step definitions for the dashboard living-update scenario, driven offline.

Exercises the REST surface end to end (seed -> inject -> dashboard) through a
FastAPI TestClient with the CT.gov fetch overridden to recorded fixtures. This
complements the MCP-level `mcp_update.feature`.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest_bdd import given, when, then, scenario, parsers

from livemeta.api.app import app, get_fetch_study, get_store
from livemeta.core import demo
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_fetch():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return fetch


@scenario("living_update.feature", "Injecting the eighth GLP-1 trial updates the dashboard")
def test_living_update_surfaces_on_dashboard():
    pass


@given("a seeded 7-trial GLP-1 MACE baseline", target_fixture="ctx")
def _seed(tmp_path):
    store = SnapshotStore(tmp_path)
    app.dependency_overrides[get_fetch_study] = _fixture_fetch
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    assert client.post("/api/reviews/demo/seed").status_code == 200
    yield {"client": client, "store": store}
    # Leave the fetch override in place (harmless fixture fetch); only the
    # per-test store override must be cleared so it can't leak to other tests.
    app.dependency_overrides.pop(get_store, None)


@when("the eighth trial is injected via the REST update endpoint", target_fixture="diff")
def _inject(ctx):
    r = ctx["client"].post(
        "/api/reviews/glp1-mace/update", json={"new_trial_id": demo.HELD_OUT_TRIAL}
    )
    assert r.status_code == 200
    return r.json()


@then("the update reports eight pooled trials")
def _eight(diff):
    assert diff["k_curr"] == 8


@then("the dashboard row shows eight trials")
def _dashboard_k(ctx):
    rows = ctx["client"].get("/api/reviews").json()
    row = next(r for r in rows if r["question_id"] == "glp1-mace")
    assert row["k"] == 8


@then(parsers.parse('the dashboard status is "{status}"'))
def _dashboard_status(ctx, status):
    rows = ctx["client"].get("/api/reviews").json()
    row = next(r for r in rows if r["question_id"] == "glp1-mace")
    assert row["status"] == status
