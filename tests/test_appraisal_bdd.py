"""Step definitions for the appraisal (RoB 2 + GRADE + sensitivity) journey."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario

from livemeta.core import rob as rob_mod
from tests import glp1_fixtures as demo
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import RobDecision
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


@scenario("appraisal.feature", "A pooled review is appraised and a RoB domain is confirmed")
def test_appraisal():
    pass


@given("a pooled review of the eight GLP-1 MACE trials", target_fixture="review")
def _review():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return run_review_collect(demo.GLP1_MACE_QUESTION, fetch)


@then("every pooled trial has a risk-of-bias assessment")
def _rob_present(review):
    assert len(review.rob) == len(review.question.trial_ids)
    assert all(len(a.domains) == 5 for a in review.rob)


@then("a leave-one-out row is produced for each trial")
def _loo_present(review):
    assert len(review.sensitivity) == review.pool.k
    assert all(r.k == review.pool.k - 1 for r in review.sensitivity)


@then("the review carries a GRADE certainty rating")
def _grade_present(review):
    assert review.grade is not None
    assert review.grade.certainty is not None
    assert len(review.grade.domains) == 5


@when("a reviewer confirms a risk-of-bias domain on the first trial", target_fixture="context")
def _confirm(review, tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_snapshot(review)
    target = review.rob[0]
    decision = RobDecision(study_id=target.study_id, domain_key="D1")
    store.save_rob_decision(review.question.id, decision)

    decisions = store.load_rob_decisions(review.question.id)
    review.rob = [rob_mod.apply_rob_decisions(a, decisions) for a in review.rob]
    store.save_snapshot(review)
    return {"store": store, "review": review, "qid": review.question.id, "target": target.study_id}


@then("that domain is marked confirmed in the audit trail")
def _confirmed(context):
    decisions = context["store"].load_rob_decisions(context["qid"])
    assert any(
        d.study_id == context["target"] and d.domain_key == "D1" for d in decisions
    )
    first = context["review"].rob[0]
    d1 = next(d for d in first.domains if d.key == "D1")
    assert d1.confirmed is True
    assert context["store"].list_versions(context["qid"]) == [1, 2]
