"""Step definitions for the living-update scenario, driven offline via fixtures."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario

from tests.glp1_fixtures import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import ReviewDiff
from livemeta.core.store import SnapshotStore
from livemeta.mcp import server

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


class _FixtureClient:
    def fetch_study(self, nct_id: str) -> dict:
        return _fetch(nct_id)

    def search_studies(self, query: str, page_size: int = 20) -> list[dict]:
        return []


@scenario("mcp_update.feature", "A new trial is added to an existing review")
def test_living_update():
    pass


@given("a saved review of the first seven GLP-1 MACE trials", target_fixture="context")
def _seed(tmp_path):
    server.set_client(_FixtureClient())
    server.set_store(SnapshotStore(tmp_path))
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    seeded = run_review_collect(q7, _fetch)
    server.get_store().save_snapshot(seeded)
    return {}


@when("the eighth trial lands via the update tool", target_fixture="diff")
def _update(context) -> ReviewDiff:
    return server.update("glp1-mace", GLP1_CVOT_TRIALS[7])


@then("the diff reports eight pooled trials")
def _eight(diff):
    assert diff.k_curr == 8


@then("the diff lists the newly added trial")
def _added(diff):
    assert GLP1_CVOT_TRIALS[7] in diff.added_trials


@then("the diff states whether the conclusion changed")
def _flag(diff):
    assert isinstance(diff.conclusion_changed, bool)
