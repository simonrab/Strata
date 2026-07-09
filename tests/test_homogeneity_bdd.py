"""Step definitions for the homogeneity-gate scenarios."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario

from livemeta.core import demo
from livemeta.core.pipeline import repool_with_diversity, run_review_collect
from livemeta.core.schema import DiversityDecision

FIXTURES = Path(__file__).parent / "fixtures"


@scenario("homogeneity.feature", "Homogeneous trials pool without a gate")
def test_homogeneous_pools_without_gate():
    pass


@scenario(
    "homogeneity.feature",
    "Withhold pooling until a reviewer confirms clinically diverse trials",
)
def test_diverse_is_withheld_then_confirmed():
    pass


# --- Homogeneous (demo) path ------------------------------------------------


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
def _run(request):
    if "question" in request.fixturenames and "fetch_study" in request.fixturenames:
        return run_review_collect(
            request.getfixturevalue("question"),
            request.getfixturevalue("fetch_study"),
        )
    q, fetch = request.getfixturevalue("diverse_run")
    return run_review_collect(q, fetch)


@then("the homogeneity gate does not require confirmation")
def _gate_open(review):
    assert review.diversity is not None
    assert review.diversity.requires_confirmation is False


@then("the pooled hazard ratio rounds to 0.86")
def _pools_086(review):
    assert review.pool is not None
    assert round(review.pool.estimate, 2) == 0.86


# --- Clinically diverse path ------------------------------------------------


@given(
    "a clinically diverse question whose trial effects scatter widely",
    target_fixture="diverse_run",
)
def _diverse_run(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    specs = {
        "NCT60000001": (0.50, 0.40, 0.62),
        "NCT60000002": (1.60, 1.30, 1.97),
        "NCT60000003": (0.70, 0.55, 0.89),
        "NCT60000004": (1.90, 1.55, 2.33),
    }

    def fetch(nct: str) -> dict:
        hr, lo, hi = specs[nct]
        return {
            "protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}},
            "resultsSection": {
                "outcomeMeasuresModule": {
                    "outcomeMeasures": [
                        {
                            "type": "PRIMARY",
                            "title": "Primary",
                            "analyses": [
                                {
                                    "paramType": "Hazard Ratio",
                                    "paramValue": str(hr),
                                    "ciLowerLimit": str(lo),
                                    "ciUpperLimit": str(hi),
                                }
                            ],
                        }
                    ]
                }
            },
        }

    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": list(specs)})
    return question, fetch


@then("pooling is withheld pending confirmation")
def _withheld(review):
    assert review.pool is None
    assert review.diversity is not None
    assert review.diversity.requires_confirmation is True


@when("a reviewer confirms the trials are combinable", target_fixture="confirmed")
def _confirm(review):
    return repool_with_diversity(review, DiversityDecision(reason="combinable"))


@then("the trials are pooled and the confirmation is recorded")
def _pooled_after_confirm(confirmed):
    assert confirmed.pool is not None
    assert confirmed.pool.k == 4
    assert confirmed.diversity is not None
    assert confirmed.diversity.confirmed is True
