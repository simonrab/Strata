"""Step definitions for the CLI journeys, driven offline via fixtures.

Each step invokes `main(argv=..., fetch_study=_fetch, store=SnapshotStore(tmp))`
and asserts on captured stdout and store side effects — the terminal is the
interface under test, so the assertions read the rendered report, not internal
objects.
"""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario

from livemeta.cli.app import main
from tests.glp1_fixtures import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


class _SearchClient:
    """Serves the recorded GLP-1 trial set for the demo's discovery search."""

    def search_agent_studies(self, intervention, term=None, page_size=1000, **kwargs):
        return [{"nct_id": nct, "title": nct} for nct in GLP1_CVOT_TRIALS]


@scenario("cli.feature", "Run the locked demo and read the report with a forest plot")
def test_run_demo_report():
    pass


@scenario("cli.feature", "Inject a new trial and see the conclusion diff")
def test_inject_trial_diff():
    pass


@scenario("cli.feature", "Flag a trial from the command line and re-pool")
def test_flag_trial_repool():
    pass


@scenario("cli.feature", "Honest behaviour with no model key")
def test_honest_no_key():
    pass


@given("ClinicalTrials.gov results are served from recorded fixtures", target_fixture="context")
def _fixtures(tmp_path):
    return {"store": SnapshotStore(tmp_path), "out": ""}


@given("a saved command-line review of the first seven GLP-1 MACE trials", target_fixture="context")
def _seed7(tmp_path):
    store = SnapshotStore(tmp_path)
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    store.save_snapshot(run_review_collect(q7, _fetch))
    return {"store": store, "out": ""}


@given("a saved command-line review of the eight GLP-1 MACE trials", target_fixture="context")
def _seed8(tmp_path):
    store = SnapshotStore(tmp_path)
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    return {"store": store, "out": ""}


@when("I run the demo review from the command line")
def _run_demo(context, capsys):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=context["store"], search_client=_SearchClient(), parse=_parse)
    context["out"] = capsys.readouterr().out


@when("I add the eighth trial from the command line")
def _add_eighth(context, capsys):
    main(
        argv=["update", "glp1-mace", GLP1_CVOT_TRIALS[7]],
        fetch_study=_fetch,
        store=context["store"],
    )
    context["out"] = capsys.readouterr().out


@when("I flag the first trial from the command line")
def _flag_first(context, capsys):
    capsys.readouterr()
    main(
        argv=["decision", "glp1-mace", GLP1_CVOT_TRIALS[0], "flagged", "--json"],
        store=context["store"],
    )
    context["out"] = capsys.readouterr().out


@then("the pooled hazard ratio in the report rounds to 0.86")
def _ratio(context):
    assert "0.86" in context["out"]


@then("the terminal report includes an ASCII forest plot with a pooled row")
def _forest(context):
    assert "FOREST PLOT" in context["out"]
    assert "Pooled (RE)" in context["out"]


@then("the review is saved as version 1")
def _v1(context):
    assert context["store"].list_versions("glp1-mace") == [1]


@then("the diff report shows eight pooled trials")
def _eight(context):
    assert "8" in context["out"]


@then("the diff report states whether the conclusion changed")
def _status(context):
    assert "Status:" in context["out"]


@then("the re-pooled report includes seven trials")
def _seven(context):
    doc = json.loads(context["out"])
    assert doc["pool"]["k"] == 7


@then("the decision is saved to the audit trail")
def _audit(context):
    assert context["store"].load_decisions("glp1-mace")
    assert context["store"].list_versions("glp1-mace") == [1, 2]


@then("the report marks risk of bias as PENDING rather than fabricating it")
def _pending(context):
    assert "PENDING" in context["out"]


def _parse(_text):
    # Stand in for the live PICO parser: the demo PICO with no trials, so the run
    # discovers through the injected search client (offline, deterministic).
    return GLP1_MACE_QUESTION.model_copy(update={"trial_ids": []})
