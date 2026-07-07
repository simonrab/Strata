"""Step definitions for the end-to-end pipeline scenario."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario, parsers

from livemeta.core import demo
from livemeta.core.pipeline import run_review_collect

FIXTURES = Path(__file__).parent / "fixtures"


@scenario("pipeline.feature", "Pool the GLP-1 MACE question to the published answer")
def test_pipeline_end_to_end():
    pass


@given("the locked GLP-1 MACE question", target_fixture="question")
def _question():
    return demo.GLP1_MACE_QUESTION


@given(
    "ClinicalTrials.gov results are served from recorded fixtures",
    target_fixture="fetch_study",
)
def _fetch_study():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return fetch


@when("the review pipeline runs", target_fixture="review")
def _run(question, fetch_study):
    return run_review_collect(question, fetch_study)


@then("every trial is extracted with provenance and none are flagged")
def _extracted(review):
    assert len(review.extractions) == 8
    assert all(not e.flagged for e in review.extractions)
    assert all(e.provenance and e.provenance[0].snippet for e in review.extractions)


@then(parsers.parse("the pooled hazard ratio rounds to {value:f}"))
def _pooled(review, value):
    assert review.pool is not None
    assert round(review.pool.estimate, 2) == value


@then("the confidence interval shows a significant cardiovascular benefit")
def _significant(review):
    assert review.pool.ci_high < 1.0


@then("the plain-language summary reports the benefit")
def _summary(review):
    assert "reduced" in review.summary.lower()
    assert review.pool.measure.value in review.summary
