"""Unit tests for re-pooling after human confirm/flag decisions.

The human-in-the-loop gate is load-bearing: a reviewer's *flag* must remove a
trial from the pool and change the estimate; a *confirm* records sign-off without
altering poolability. These assertions guard that contract.
"""

import json
from pathlib import Path

from livemeta.core import demo
from livemeta.core.pipeline import repool_with_decisions, run_review_collect
from livemeta.core.schema import EffectMeasure, PICO, PoolMethod, Question, ReviewDecision

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


def _continuous_question(specs: dict[str, tuple]) -> tuple[Question, callable]:
    """A measure=MD question plus a fetch serving CT.gov-shaped continuous results.

    `specs` maps nct -> (m1, sd1, n1, m2, sd2, n2).
    """
    from tests.test_extract import _ctgov_continuous

    question = Question(
        id="q-continuous",
        text="Continuous outcome",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="score"),
        measure=EffectMeasure.MD,
        trial_ids=list(specs),
    )

    def fetch(nct: str) -> dict:
        return _ctgov_continuous(nct, *specs[nct])

    return question, fetch


def _binary_question(specs: dict[str, tuple], measure=EffectMeasure.OR):
    """A binary question plus a fetch serving CT.gov-shaped 2x2 results.

    `specs` maps nct -> (a, n1, c, n2).
    """
    from tests.test_extract import _ctgov_binary

    question = Question(
        id="q-binary",
        text="Binary outcome",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="event"),
        measure=measure,
        trial_ids=list(specs),
    )

    def fetch(nct: str) -> dict:
        return _ctgov_binary(nct, *specs[nct])

    return question, fetch


def _baseline():
    return run_review_collect(demo.GLP1_MACE_QUESTION, _fetch)


def test_baseline_pools_all_eight():
    review = _baseline()
    assert review.pool is not None
    assert review.pool.k == 8
    assert round(review.pool.estimate, 2) == 0.86


def test_flagging_a_trial_removes_it_from_the_pool():
    baseline = _baseline()
    target = baseline.extractions[0].study_id

    repooled = repool_with_decisions(
        baseline,
        [ReviewDecision(study_id=target, decision="flagged", reason="reviewer flagged")],
    )

    assert repooled.pool is not None
    assert repooled.pool.k == 7
    pooled_ids = {s.study_id for s in repooled.pool.studies}
    assert target not in pooled_ids

    flagged = next(e for e in repooled.extractions if e.study_id == target)
    assert flagged.flagged is True
    assert flagged.flag_reason == "reviewer flagged"


def test_confirming_a_trial_keeps_it_and_records_signoff():
    baseline = _baseline()
    target = baseline.extractions[0].study_id

    repooled = repool_with_decisions(
        baseline, [ReviewDecision(study_id=target, decision="confirmed")]
    )

    assert repooled.pool is not None
    assert repooled.pool.k == 8
    confirmed = next(e for e in repooled.extractions if e.study_id == target)
    assert confirmed.confirmed is True
    assert confirmed.flagged is False


def test_summary_is_recomputed_after_repool():
    baseline = _baseline()
    ids = [e.study_id for e in baseline.extractions]

    # Flag all but two trials — the estimate and k in the summary must update.
    decisions = [ReviewDecision(study_id=i, decision="flagged") for i in ids[:6]]
    repooled = repool_with_decisions(baseline, decisions)

    assert repooled.pool is not None
    assert repooled.pool.k == 2
    assert "2 trials" in repooled.summary


def test_run_fetches_every_trial_with_no_cap(monkeypatch):
    # No run cap: a review fetches all candidates (concurrently). 40 trials means
    # 40 fetches, all pooled. (Fast Python engine so 40 studies pool quickly.)
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    sample = _fetch("NCT01179048")
    fetched: list[str] = []

    def counting_fetch(nct: str) -> dict:
        fetched.append(nct)
        return sample

    question = demo.GLP1_MACE_QUESTION.model_copy(
        update={"trial_ids": [f"NCT{i:08d}" for i in range(40)]}
    )
    result = run_review_collect(question, counting_fetch)

    assert len(fetched) == 40
    assert result.pool is not None
    assert result.pool.k == 40


def test_rob_is_scoped_to_pooled_trials_only(monkeypatch):
    # RoB must appraise only the trials that make the pool, not every candidate:
    # non-poolable trials (no extractable HR) are excluded from the RoB list.
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    good = ["NCT01179048", "NCT01720446", "NCT02465515"]  # real fixtures with HRs
    bad = ["NCTBAD0001", "NCTBAD0002"]  # no results section -> flagged, not pooled

    def fetch(nct: str) -> dict:
        if nct in bad:
            return {"protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}}}
        return _fetch(nct)

    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": good + bad})
    result = run_review_collect(question, fetch)

    assert result.pool is not None
    assert result.pool.k == 3
    # RoB covers exactly the 3 pooled trials — the 2 unpoolable ones are excluded.
    assert len(result.rob) == 3
    assert {r.study_id for r in result.rob} == set(good)


# --- Measure-polymorphism: continuous + rare-event end to end ---------------


def test_pipeline_pools_continuous_end_to_end(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    question, fetch = _continuous_question(
        {
            "NCT20000001": (10.0, 2.0, 50, 8.0, 2.5, 50),
            "NCT20000002": (12.0, 3.0, 60, 9.0, 3.0, 60),
        }
    )
    result = run_review_collect(question, fetch)

    assert result.pool is not None
    assert result.pool.measure == EffectMeasure.MD
    assert result.pool.k == 2
    # MD pools on the natural scale — estimate equals its own log field (no exp()).
    assert result.pool.estimate == result.pool.estimate_log
    assert 2.0 < result.pool.estimate < 3.0
    # The extraction carried the continuous variant.
    assert all(e.continuous is not None for e in result.extractions if not e.flagged)


def test_pipeline_routes_rare_binary_to_peto(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    # Sparse events with a zero cell — the case inverse-variance can't handle.
    question, fetch = _binary_question(
        {
            "NCT30000001": (0, 100, 3, 100),
            "NCT30000002": (2, 200, 4, 200),
        },
        measure=EffectMeasure.OR,
    )
    result = run_review_collect(question, fetch)

    assert result.pool is not None
    assert result.pool.pool_method == PoolMethod.PETO
    assert result.pool.k == 2


def test_pipeline_aggregates_assumptions_from_studies():
    # The HR demo derives each study's SE from its reported CI — those
    # conversions must surface on the pooled result's assumptions ledger.
    review = _baseline()
    assert review.pool is not None
    codes = {a.code for a in review.pool.assumptions}
    assert "log_ratio_se_from_ci" in codes
    # One assumption per pooled trial (8 in the demo).
    assert sum(1 for a in review.pool.assumptions if a.code == "log_ratio_se_from_ci") == 8


# --- Eligibility screening: screened-out trials never reach the pool --------


def _hr_study(nct: str, hr: float, lo: float, hi: float, eligibility: str = "") -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": nct},
            "eligibilityModule": {"eligibilityCriteria": eligibility},
        },
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


class _StubParsed:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _PerTrialScreenLLM:
    """Judges a trial ineligible when its eligibility text carries PEDIATRIC.

    Only the screen call is stubbed with intent; every other model call in the
    run (RoB, GRADE) gets that request's default model, mirroring a real client
    returning the requested output shape.
    """

    class _Messages:
        def parse(self, **kwargs):
            from livemeta.core.screen import _ScreenJudged

            fmt = kwargs.get("output_format")
            if fmt is _ScreenJudged:
                content = kwargs["messages"][0]["content"]
                if "PEDIATRIC" in content:
                    return _StubParsed(
                        _ScreenJudged(
                            eligible=False,
                            domain="population",
                            reason="Enrolled children, not the adult population.",
                            quote="Ages 6-17 years.",
                        )
                    )
                return _StubParsed(_ScreenJudged(eligible=True, reason="Matches the PICO."))
            return _StubParsed(fmt())  # RoB / GRADE: default judgment

    @property
    def messages(self):
        return _PerTrialScreenLLM._Messages()


def test_screened_out_trial_never_reaches_the_pool(monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    good = {
        "NCT70000001": _hr_study("NCT70000001", 0.80, 0.70, 0.92, "Adults with T2D."),
        "NCT70000002": _hr_study("NCT70000002", 0.85, 0.74, 0.98, "Adults with T2D."),
        "NCT70000003": _hr_study("NCT70000003", 0.88, 0.77, 1.01, "Adults with T2D."),
    }
    # Ineligible trial: a valid HR that WOULD pool if the screen didn't drop it.
    ineligible = {
        "NCT79999999": _hr_study("NCT79999999", 0.50, 0.40, 0.62, "PEDIATRIC: ages 6-17.")
    }
    studies = {**good, **ineligible}

    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": list(studies)})
    result = run_review_collect(
        question, lambda nct: studies[nct], llm_client=_PerTrialScreenLLM()
    )

    # The eligible three pool; the pediatric trial is screened out despite a valid HR.
    assert result.pool is not None
    assert result.pool.k == 3
    pooled_ids = {s.study_id for s in result.pool.studies}
    assert "NCT79999999" not in pooled_ids

    # It is recorded as a clinical eligibility exclusion, with provenance…
    excluded = next(d for d in result.screening if d.decision == "excluded")
    assert excluded.study_id == "NCT79999999"
    assert excluded.domain == "population"
    assert excluded.by_claude is True
    assert excluded.quote is not None
    # …and it never received an extraction record.
    assert all(e.study_id != "NCT79999999" for e in result.extractions)

    # The PRISMA funnel shows the real eligibility stage.
    flow = result.prisma
    assert flow is not None
    assert "NCT79999999" in {sid for e in flow.excluded for sid in e.study_ids}


# --- Homogeneity gate -------------------------------------------------------


def test_demo_passes_gate_and_still_pools_086(monkeypatch):
    # The GLP-1 demo is clinically homogeneous and low-heterogeneity (I² ~45%,
    # "moderate"), so the gate must NOT fire — it pools straight through to 0.86.
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    review = _baseline()
    assert review.pool is not None
    assert round(review.pool.estimate, 2) == 0.86
    assert review.diversity is not None
    assert review.diversity.requires_confirmation is False


def test_gate_abstains_until_confirmed(monkeypatch):
    # A deliberately heterogeneous set (substantial I²) withholds the pool until
    # a reviewer confirms. The diversity assessment is still populated.
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    # HRs that scatter widely -> high I².
    specs = {
        "NCT60000001": (0.50, 0.40, 0.62),
        "NCT60000002": (1.60, 1.30, 1.97),
        "NCT60000003": (0.70, 0.55, 0.89),
        "NCT60000004": (1.90, 1.55, 2.33),
    }

    def fetch(nct):
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
    review = run_review_collect(question, fetch)

    assert review.diversity is not None
    assert review.diversity.requires_confirmation is True
    assert review.pool is None
    assert "withheld" in review.summary.lower()


def test_repool_after_diversity_confirmation(monkeypatch):
    from livemeta.core.pipeline import repool_with_diversity
    from livemeta.core.schema import DiversityDecision

    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    specs = {
        "NCT60000001": (0.50, 0.40, 0.62),
        "NCT60000002": (1.60, 1.30, 1.97),
        "NCT60000003": (0.70, 0.55, 0.89),
        "NCT60000004": (1.90, 1.55, 2.33),
    }

    def fetch(nct):
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
    withheld = run_review_collect(question, fetch)
    assert withheld.pool is None

    confirmed = repool_with_diversity(withheld, DiversityDecision(reason="clinically combinable"))
    assert confirmed.pool is not None
    assert confirmed.pool.k == 4
    assert confirmed.diversity is not None
    assert confirmed.diversity.confirmed is True
