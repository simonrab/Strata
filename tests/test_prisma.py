"""PRISMA 2020 record-flow builder.

The flow diagram is the systematic-review artifact that makes a synthesis
reproducible, so it must be *derived* from the run, never hand-set, and it must
reconcile at every stage. These tests pin the funnel arithmetic (identified =
screened + duplicates; screened = assessed + not_retrieved; assessed = included
+ exclusions), the real exclusion reasons, and that the pipeline attaches it.
"""

import json
from pathlib import Path

from tests import glp1_fixtures as demo
from livemeta.core.prisma import build_prisma
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import (
    BinaryArm,
    BinaryEffect,
    DiversityAssessment,
    EligibilityDecision,
    PICO,
    Provenance,
    Question,
    ReviewResult,
    TrialExtraction,
    ValidationIssue,
    ValidationResult,
    EffectMeasure,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


def _q(trial_ids, measure=EffectMeasure.HR) -> Question:
    return Question(
        id="q",
        text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=measure,
        trial_ids=list(trial_ids),
    )


def _passed(sid: str) -> tuple[TrialExtraction, ValidationResult]:
    ext = TrialExtraction(study_id=sid, label=sid, hr=0.8, ci_low=0.7, ci_high=0.9)
    val = ValidationResult(study_id=sid, passed=True)
    return ext, val


def _flagged(sid: str, reason: str) -> tuple[TrialExtraction, ValidationResult]:
    ext = TrialExtraction(study_id=sid, label=sid, flagged=True, flag_reason=reason)
    val = ValidationResult(
        study_id=sid,
        passed=False,
        issues=[ValidationIssue(study_id=sid, code="not_extracted", message=reason)],
    )
    return ext, val


def _validation_failed(sid: str, code: str) -> tuple[TrialExtraction, ValidationResult]:
    # Extracted (not flagged) but fails the deterministic gate.
    ext = TrialExtraction(
        study_id=sid,
        label=sid,
        binary=BinaryEffect(
            study_id=sid,
            label=sid,
            treatment=BinaryArm(events=200, total=100),  # events > total
            control=BinaryArm(events=5, total=100),
        ),
    )
    val = ValidationResult(
        study_id=sid,
        passed=False,
        issues=[ValidationIssue(study_id=sid, code=code, message="bad")],
    )
    return ext, val


def _result(
    trial_ids, extractions, validations, pool=None, diversity=None, screening=None
) -> ReviewResult:
    return ReviewResult(
        question=_q(trial_ids),
        screening=screening or [],
        extractions=extractions,
        validations=validations,
        pool=pool,
        diversity=diversity,
    )


def _assert_reconciles(flow) -> None:
    assert flow.identified == flow.screened + flow.duplicates_removed
    assert flow.screened == flow.assessed + flow.not_retrieved
    assert flow.assessed == flow.included + sum(e.count for e in flow.excluded)


# --- Unit: the funnel arithmetic and buckets --------------------------------


def test_all_included_no_exclusions():
    ids = ["NCT1", "NCT2", "NCT3"]
    exts, vals = zip(*(_passed(i) for i in ids))
    flow = build_prisma(_result(ids, list(exts), list(vals)))

    assert flow.identified == 3
    assert flow.duplicates_removed == 0
    assert flow.screened == 3
    assert flow.not_retrieved == 0
    assert flow.assessed == 3
    assert flow.excluded == []
    assert flow.included == 3
    _assert_reconciles(flow)


def test_duplicates_are_removed_before_screening():
    ids = ["NCT1", "NCT1", "NCT2"]
    e1, v1 = _passed("NCT1")
    e2, v2 = _passed("NCT2")
    flow = build_prisma(_result(ids, [e1, e2], [v1, v2]))

    assert flow.identified == 3
    assert flow.duplicates_removed == 1
    assert flow.screened == 2
    assert flow.included == 2
    _assert_reconciles(flow)


def test_retrieval_failure_is_a_screening_drop_not_an_exclusion():
    e_ok, v_ok = _passed("NCT1")
    e_bad, v_bad = _flagged("NCT2", "Could not retrieve from ClinicalTrials.gov: 503")
    flow = build_prisma(_result(["NCT1", "NCT2"], [e_ok, e_bad], [v_ok, v_bad]))

    assert flow.not_retrieved == 1
    assert flow.assessed == 1
    assert flow.excluded == []  # a not-retrieved report is not an eligibility exclusion
    assert flow.included == 1
    _assert_reconciles(flow)


def test_no_effect_data_is_an_eligibility_exclusion_with_reason():
    e_ok, v_ok = _passed("NCT1")
    e_ok2, v_ok2 = _passed("NCT2")
    e_bad, v_bad = _flagged("NCT3", "No hazard-ratio analysis found in structured results.")
    flow = build_prisma(
        _result(["NCT1", "NCT2", "NCT3"], [e_ok, e_ok2, e_bad], [v_ok, v_ok2, v_bad])
    )

    assert flow.included == 2
    assert len(flow.excluded) == 1
    bucket = flow.excluded[0]
    assert bucket.reason == "No extractable effect data reported"
    assert bucket.count == 1
    assert bucket.study_ids == ["NCT3"]
    _assert_reconciles(flow)


def test_validation_failure_bucketed_by_issue_code():
    e_ok, v_ok = _passed("NCT1")
    e_ok2, v_ok2 = _passed("NCT2")
    e_bad, v_bad = _validation_failed("NCT3", "events_gt_total")
    flow = build_prisma(
        _result(["NCT1", "NCT2", "NCT3"], [e_ok, e_ok2, e_bad], [v_ok, v_ok2, v_bad])
    )

    assert flow.included == 2
    assert flow.excluded[0].reason == "Events exceed arm total"
    assert flow.excluded[0].study_ids == ["NCT3"]
    _assert_reconciles(flow)


def test_same_reason_aggregates_into_one_bucket():
    ids = ["NCT1", "NCT2", "NCT3"]
    e1, v1 = _flagged("NCT1", "No structured 2x2 event counts found.")
    e2, v2 = _flagged("NCT2", "No hazard-ratio analysis found in structured results.")
    e3, v3 = _passed("NCT3")
    flow = build_prisma(_result(ids, [e1, e2, e3], [v1, v2, v3]))

    assert len(flow.excluded) == 1
    assert flow.excluded[0].count == 2
    assert set(flow.excluded[0].study_ids) == {"NCT1", "NCT2"}
    _assert_reconciles(flow)


def test_identified_by_source_classifies_ids():
    ids = ["NCT1", "NCT2", "PMC7", "MED:42"]
    exts, vals = zip(*(_passed(i) for i in ids))
    flow = build_prisma(_result(ids, list(exts), list(vals)))

    assert flow.identified_by_source["ClinicalTrials.gov"] == 2
    assert flow.identified_by_source["Europe PMC"] == 2


def test_withheld_pool_records_synthesis_note():
    ids = ["NCT1", "NCT2"]
    exts, vals = zip(*(_passed(i) for i in ids))
    diversity = DiversityAssessment(requires_confirmation=True, confirmed=False)
    flow = build_prisma(_result(ids, list(exts), list(vals), diversity=diversity))

    assert flow.included == 2
    assert flow.included_in_synthesis == 0
    assert "withheld" in flow.synthesis_note.lower()


def test_abstain_when_too_few_eligible():
    e_ok, v_ok = _passed("NCT1")
    e_bad, v_bad = _flagged("NCT2", "No hazard-ratio analysis found in structured results.")
    flow = build_prisma(_result(["NCT1", "NCT2"], [e_ok, e_bad], [v_ok, v_bad]))

    assert flow.included == 1
    assert flow.included_in_synthesis == 0
    assert "abstain" in flow.synthesis_note.lower()


# --- Eligibility screening: real clinical exclusions in the funnel -----------


def test_screen_exclusion_is_an_eligibility_bucket_before_extraction():
    # A trial excluded at the clinical screen has no extraction record; it must
    # be bucketed as a real eligibility exclusion (by PICO domain), NOT counted
    # as a not-retrieved report, and the funnel must still reconcile.
    e_ok, v_ok = _passed("NCT1")
    e_ok2, v_ok2 = _passed("NCT2")
    screening = [
        EligibilityDecision(study_id="NCT1", decision="included"),
        EligibilityDecision(study_id="NCT2", decision="included"),
        EligibilityDecision(
            study_id="NCT3",
            decision="excluded",
            domain="population",
            reason="Enrolled children, not the adult population.",
        ),
    ]
    flow = build_prisma(
        _result(["NCT1", "NCT2", "NCT3"], [e_ok, e_ok2], [v_ok, v_ok2], screening=screening)
    )

    assert flow.not_retrieved == 0
    assert flow.included == 2
    assert len(flow.excluded) == 1
    assert flow.excluded[0].reason == "Ineligible population"
    assert flow.excluded[0].study_ids == ["NCT3"]
    assert flow.excluded[0].stage == "screening"  # clinical eligibility, not a data drop
    _assert_reconciles(flow)


def test_exclusion_stage_separates_clinical_screen_from_data_failures():
    # A clinical-screen exclusion is tagged "screening"; a no-effect-data / failed
    # validation exclusion is tagged "reports", so the funnel can show the two
    # PRISMA exclusion kinds distinctly.
    e_ok, v_ok = _passed("NCT1")
    e_ok2, v_ok2 = _passed("NCT2")
    e_bad, v_bad = _flagged("NCT4", "No hazard-ratio analysis found in structured results.")
    screening = [
        EligibilityDecision(study_id="NCT1", decision="included"),
        EligibilityDecision(study_id="NCT2", decision="included"),
        EligibilityDecision(study_id="NCT3", decision="excluded", domain="design"),
        EligibilityDecision(study_id="NCT4", decision="included"),
    ]
    flow = build_prisma(
        _result(
            ["NCT1", "NCT2", "NCT3", "NCT4"],
            [e_ok, e_ok2, e_bad],
            [v_ok, v_ok2, v_bad],
            screening=screening,
        )
    )
    by_stage = {e.reason: e.stage for e in flow.excluded}
    assert by_stage["Ineligible study design"] == "screening"
    assert by_stage["No extractable effect data reported"] == "reports"
    _assert_reconciles(flow)


# --- Integration: the pipeline attaches a reconciled flow --------------------


def test_demo_baseline_flow_is_eight_in_eight_out():
    review = run_review_collect(demo.GLP1_MACE_QUESTION, _fetch)
    assert review.prisma is not None
    flow = review.prisma
    assert flow.identified == 8
    assert flow.included == 8
    assert flow.included_in_synthesis == 8
    assert flow.excluded == []
    _assert_reconciles(flow)


def test_pipeline_flow_counts_unpoolable_exclusions(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    good = ["NCT01179048", "NCT01720446", "NCT02465515"]
    bad = ["NCTBAD1", "NCTBAD2"]  # no results section -> no extractable effect data

    def fetch(nct: str) -> dict:
        if nct in bad:
            return {"protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}}}
        return _fetch(nct)

    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": good + bad})
    review = run_review_collect(question, fetch)

    flow = review.prisma
    assert flow is not None
    assert flow.identified == 5
    assert flow.included == 3
    assert flow.included_in_synthesis == 3
    excluded_ids = {sid for e in flow.excluded for sid in e.study_ids}
    assert excluded_ids == set(bad)
    _assert_reconciles(flow)
