"""Step definitions for the end-to-end pipeline scenario."""

import json
from pathlib import Path

from pytest_bdd import given, when, then, scenario, parsers

from tests import glp1_fixtures as demo
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import EffectMeasure, PICO, PoolMethod, Question

FIXTURES = Path(__file__).parent / "fixtures"


@scenario("pipeline.feature", "Pool the GLP-1 MACE question to the published answer")
def test_pipeline_end_to_end():
    pass


@scenario("pipeline.feature", "Screen out an ineligible trial before pooling")
def test_pipeline_screening():
    pass


@scenario("pipeline.feature", "Pool a continuous outcome on the natural scale")
def test_pipeline_continuous():
    pass


@scenario("pipeline.feature", "Pool a rare binary outcome with Peto")
def test_pipeline_rare_binary():
    pass


@scenario(
    "pipeline.feature",
    "Read a trial that lacks structured CT.gov results from its abstract",
)
def test_pipeline_europepmc_text():
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


# --- Continuous outcome scenario --------------------------------------------


@given(
    "a continuous-outcome question with two trials reporting mean, SD and n",
    target_fixture="continuous_run",
)
def _continuous_run(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    from tests.test_extract import _ctgov_continuous

    specs = {
        "NCT40000001": (10.0, 2.0, 50, 8.0, 2.5, 50),
        "NCT40000002": (12.0, 3.0, 60, 9.0, 3.0, 60),
    }
    question = Question(
        id="q-bdd-continuous",
        text="Continuous outcome",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="score"),
        measure=EffectMeasure.MD,
        trial_ids=list(specs),
    )
    return question, lambda nct: _ctgov_continuous(nct, *specs[nct])


@when("the review pipeline runs", target_fixture="review")
def _run_generic(request):
    # Reuse the locked-question fixtures when present; otherwise a scenario-local run.
    if "screening_run" in request.fixturenames:
        q, fetch, llm = request.getfixturevalue("screening_run")
        return run_review_collect(q, fetch, llm_client=llm)
    if "question" in request.fixturenames and "fetch_study" in request.fixturenames:
        return run_review_collect(
            request.getfixturevalue("question"),
            request.getfixturevalue("fetch_study"),
        )
    if "continuous_run" in request.fixturenames:
        q, fetch = request.getfixturevalue("continuous_run")
        return run_review_collect(q, fetch)
    if "rare_binary_run" in request.fixturenames:
        q, fetch = request.getfixturevalue("rare_binary_run")
        return run_review_collect(q, fetch)
    q, fetch, llm = request.getfixturevalue("europepmc_run")
    return run_review_collect(q, fetch, llm_client=llm)


# --- Eligibility screening scenario -----------------------------------------


@given(
    "three eligible trials and one enrolling the wrong population",
    target_fixture="screening_run",
)
def _screening_run(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    from tests.test_pipeline import _PerTrialScreenLLM, _hr_study

    studies = {
        "NCT80000001": _hr_study("NCT80000001", 0.80, 0.70, 0.92, "Adults with T2D."),
        "NCT80000002": _hr_study("NCT80000002", 0.85, 0.74, 0.98, "Adults with T2D."),
        "NCT80000003": _hr_study("NCT80000003", 0.88, 0.77, 1.01, "Adults with T2D."),
        "NCT89999999": _hr_study("NCT89999999", 0.50, 0.40, 0.62, "PEDIATRIC: ages 6-17."),
    }
    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": list(studies)})
    return question, lambda nct: studies[nct], _PerTrialScreenLLM()


@then("the ineligible trial is excluded at the eligibility screen with a reason")
def _screen_excluded(review):
    excluded = [d for d in review.screening if d.decision == "excluded"]
    assert len(excluded) == 1
    assert excluded[0].study_id == "NCT89999999"
    assert excluded[0].reason
    assert excluded[0].domain == "population"


@then("only the eligible trials reach the pool")
def _only_eligible_pooled(review):
    assert review.pool is not None
    assert review.pool.k == 3
    assert "NCT89999999" not in {s.study_id for s in review.pool.studies}


@then("the PRISMA funnel records the eligibility exclusion")
def _prisma_records_exclusion(review):
    assert review.prisma is not None
    excluded_ids = {sid for e in review.prisma.excluded for sid in e.study_ids}
    assert "NCT89999999" in excluded_ids


@given(
    "a question whose trial is a Europe PMC publication read by Claude",
    target_fixture="europepmc_run",
)
def _europepmc_run():
    from livemeta.core.extract_text import ExtractedEffect
    from tests.test_extract_text import _StubLLM

    doc = {
        "id": "PMID:12345678",
        "source": "europepmc",
        "title": "A published cardiovascular trial",
        "abstract": "The primary endpoint occurred in 40/500 vs 60/500.",
        "full_text": "",
        "tables": [],
    }
    question = Question(
        id="q-bdd-epmc",
        text="Published-only trial",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="event"),
        measure=EffectMeasure.RR,
        trial_ids=["PMID:12345678"],
    )
    parsed = ExtractedEffect(
        found=True,
        confidence="high",
        variant="binary",
        events_treatment=40,
        total_treatment=500,
        events_control=60,
        total_control=500,
        source_snippet="The primary endpoint occurred in 40/500 vs 60/500.",
    )
    return question, lambda ref: doc, _StubLLM(parsed)


@then("the trial is extracted from the published text with provenance")
def _text_extracted(review):
    [ext] = review.extractions
    assert not ext.flagged
    assert ext.binary is not None
    assert ext.provenance and "40/500" in ext.provenance[0].snippet


@then("the pooled mean difference stays on the natural scale")
def _md_natural(review):
    assert review.pool is not None
    assert review.pool.measure == EffectMeasure.MD
    assert review.pool.estimate == review.pool.estimate_log


@then("each pooled study carries a provenance snippet")
def _study_provenance(review):
    pooled = [e for e in review.extractions if not e.flagged]
    assert pooled
    assert all(e.provenance and e.provenance[0].snippet for e in pooled)


# --- Rare binary scenario ---------------------------------------------------


@given(
    "a rare binary-outcome question with a zero-event arm",
    target_fixture="rare_binary_run",
)
def _rare_binary_run(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    from tests.test_extract import _ctgov_binary

    specs = {
        "NCT50000001": (0, 100, 3, 100),
        "NCT50000002": (2, 200, 4, 200),
    }
    question = Question(
        id="q-bdd-rare",
        text="Rare binary outcome",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="event"),
        measure=EffectMeasure.OR,
        trial_ids=list(specs),
    )
    return question, lambda nct: _ctgov_binary(nct, *specs[nct])


@then("the pool uses the Peto one-step odds ratio")
def _peto(review):
    assert review.pool is not None
    assert review.pool.pool_method == PoolMethod.PETO
