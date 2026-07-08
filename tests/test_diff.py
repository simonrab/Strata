"""Living diff: does adding a trial move the estimate or change the conclusion?

Conclusion change = the statistical significance flips (CI crossing 1) or the
direction of effect flips (estimate crossing 1).
"""

import math

from livemeta.core.diff import diff_reviews, status_from_diff
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)


def _review(estimate: float, ci_low: float, ci_high: float, *, trial_ids=None) -> ReviewResult:
    q = Question(
        id="q-demo",
        text="demo",
        pico=PICO(population="p", intervention="drug", comparator="placebo", outcome="MACE"),
        trial_ids=trial_ids or [],
    )
    pool = PoolResult(
        measure=EffectMeasure.HR,
        engine="python",
        k=len(q.trial_ids) or 5,
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=CIMethod.HKSJ,
        estimate_log=math.log(estimate),
        se_log=0.05,
        ci_low_log=math.log(ci_low),
        ci_high_log=math.log(ci_high),
        tau2=0.01,
        i2=20.0,
        q=5.0,
        q_p=0.4,
    )
    return ReviewResult(question=q, pool=pool)


def test_no_change():
    prev = _review(0.86, 0.79, 0.94)
    curr = _review(0.86, 0.79, 0.94)
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert d.significance_changed is False
    assert d.direction_changed is False
    assert d.conclusion_changed is False
    assert d.delta == 0.0


def test_estimate_moves_but_conclusion_holds():
    prev = _review(0.86, 0.79, 0.94)
    curr = _review(0.82, 0.75, 0.90)  # still a significant benefit
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert d.conclusion_changed is False
    assert round(d.delta, 2) == -0.04


def test_significance_flip_changes_conclusion():
    prev = _review(0.86, 0.79, 0.94)  # significant benefit
    curr = _review(0.92, 0.84, 1.01)  # CI now crosses 1 -> no longer significant
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert d.significance_changed is True
    assert d.direction_changed is False
    assert d.conclusion_changed is True


def test_direction_flip_changes_conclusion():
    prev = _review(0.86, 0.79, 0.94)  # benefit
    curr = _review(1.15, 1.03, 1.28)  # harm
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert d.direction_changed is True
    assert d.conclusion_changed is True


def test_added_trials_detected():
    prev = _review(0.86, 0.79, 0.94, trial_ids=["A", "B"])
    curr = _review(0.85, 0.78, 0.93, trial_ids=["A", "B", "C"])
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert d.added_trials == ["C"]
    assert d.k_prev == 2
    assert d.k_curr == 3


# --- Slice 5: the dashboard's three-state status is derived from the diff ------


def test_status_unchanged_when_estimate_barely_moves():
    prev = _review(0.86, 0.79, 0.94)
    curr = _review(0.86, 0.79, 0.94)
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert status_from_diff(d) == "unchanged"


def test_status_estimate_updated_when_estimate_moves_but_conclusion_holds():
    prev = _review(0.86, 0.79, 0.94)
    curr = _review(0.82, 0.75, 0.90)  # still a significant benefit
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert status_from_diff(d) == "estimate-updated"


def test_status_conclusion_moved_when_significance_flips():
    prev = _review(0.86, 0.79, 0.94)  # significant benefit
    curr = _review(0.92, 0.84, 1.01)  # CI now crosses 1 -> no longer significant
    d = diff_reviews(prev, curr, previous_version=1, current_version=2)
    assert status_from_diff(d) == "conclusion-moved"
