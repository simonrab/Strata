"""Step definitions for the human confirm/flag → re-pool journey."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario

from tests import glp1_fixtures as demo
from livemeta.core.pipeline import repool_with_decisions, run_review_collect
from livemeta.core.schema import ReviewDecision
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


@scenario("human_review.feature", "A reviewer flags a trial and the pool re-runs without it")
def test_human_review():
    pass


@given("a pooled review of the eight GLP-1 MACE trials", target_fixture="review")
def _review():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return run_review_collect(demo.GLP1_MACE_QUESTION, fetch)


@when("a reviewer flags the first trial for review", target_fixture="context")
def _flag(review, tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_snapshot(review)
    target = review.extractions[0].study_id
    decision = ReviewDecision(study_id=target, decision="flagged", reason="unclear arm")
    store.save_decision(review.question.id, decision)
    repooled = repool_with_decisions(review, store.load_decisions(review.question.id))
    store.save_snapshot(repooled)
    return {"store": store, "repooled": repooled, "target": target, "qid": review.question.id}


@then("the re-pooled review includes seven trials")
def _seven(context):
    assert context["repooled"].pool is not None
    assert context["repooled"].pool.k == 7


@then("the flagged trial is excluded from the pool")
def _excluded(context):
    pooled_ids = {s.study_id for s in context["repooled"].pool.studies}
    assert context["target"] not in pooled_ids


@then("the decision is saved to the audit trail")
def _saved(context):
    decisions = context["store"].load_decisions(context["qid"])
    assert any(
        d.study_id == context["target"] and d.decision == "flagged" for d in decisions
    )
    # Re-pool created a second snapshot version — the audit trail grew.
    assert context["store"].list_versions(context["qid"]) == [1, 2]
