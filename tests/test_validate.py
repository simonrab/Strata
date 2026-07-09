"""Deterministic validation gate — plain code, runs before any pooling.

Cochrane-aligned sanity checks: events cannot exceed arm totals, totals must be
positive, counts must be non-negative, and a reported percentage must match the
count. Anything that fails is flagged for review, never pooled.
"""

from livemeta.core.schema import (
    BinaryArm,
    BinaryEffect,
    ContinuousArm,
    ContinuousEffect,
    EffectMeasure,
    TrialExtraction,
)
from livemeta.core.validate import validate_binary, validate_extractions


def _effect(et, nt, ec, nc, *, pct_t=None, pct_c=None, sid="S1"):
    return BinaryEffect(
        study_id=sid,
        label=sid,
        treatment=BinaryArm(events=et, total=nt, reported_pct=pct_t),
        control=BinaryArm(events=ec, total=nc, reported_pct=pct_c),
    )


def test_valid_effect_passes():
    [res] = validate_binary([_effect(100, 1000, 120, 1000)])
    assert res.passed
    assert res.issues == []


def test_events_exceeding_total_is_flagged():
    [res] = validate_binary([_effect(1100, 1000, 120, 1000)])
    assert not res.passed
    assert any(i.code == "events_gt_total" for i in res.issues)


def test_negative_count_is_flagged():
    [res] = validate_binary([_effect(-5, 1000, 120, 1000)])
    assert not res.passed
    assert any(i.code == "negative_count" for i in res.issues)


def test_non_positive_total_is_flagged():
    [res] = validate_binary([_effect(0, 0, 120, 1000)])
    assert not res.passed
    assert any(i.code == "non_positive_total" for i in res.issues)


def test_percentage_mismatch_is_flagged():
    # 100/1000 = 10.0%, but the source printed 25.0% -> conflict.
    [res] = validate_binary([_effect(100, 1000, 120, 1000, pct_t=25.0)])
    assert not res.passed
    assert any(i.code == "pct_mismatch" for i in res.issues)


def test_percentage_within_tolerance_passes():
    # 130/1000 = 13.0%, source printed 13.0% -> matches.
    [res] = validate_binary([_effect(130, 1000, 149, 1000, pct_t=13.0, pct_c=14.9)])
    assert res.passed


def test_mixed_batch_partitions_pass_and_flag():
    results = validate_binary(
        [_effect(100, 1000, 120, 1000, sid="ok"), _effect(50, 10, 5, 100, sid="bad")]
    )
    by_id = {r.study_id: r for r in results}
    assert by_id["ok"].passed
    assert not by_id["bad"].passed


# --- validate_extractions dispatcher (measure-polymorphic) ------------------


def _ratio_ext(sid, hr, lo, hi):
    return TrialExtraction(
        study_id=sid, label=sid, measure=EffectMeasure.HR, hr=hr, ci_low=lo, ci_high=hi
    )


def _binary_ext(sid, a, n1, c, n2):
    return TrialExtraction(
        study_id=sid,
        label=sid,
        measure=EffectMeasure.RR,
        binary=BinaryEffect(
            study_id=sid,
            label=sid,
            treatment=BinaryArm(events=a, total=n1),
            control=BinaryArm(events=c, total=n2),
        ),
    )


def _continuous_ext(sid, m1, sd1, n1, m2, sd2, n2):
    return TrialExtraction(
        study_id=sid,
        label=sid,
        measure=EffectMeasure.MD,
        continuous=ContinuousEffect(
            study_id=sid,
            label=sid,
            treatment=ContinuousArm(mean=m1, sd=sd1, n=n1),
            control=ContinuousArm(mean=m2, sd=sd2, n=n2),
        ),
    )


def test_validate_extractions_routes_ratio():
    [res] = validate_extractions([_ratio_ext("R", 0.86, 0.79, 0.94)])
    assert res.passed


def test_validate_extractions_routes_binary():
    good = validate_extractions([_binary_ext("ok", 40, 500, 60, 500)])[0]
    assert good.passed
    bad = validate_extractions([_binary_ext("bad", 600, 500, 60, 500)])[0]
    assert not bad.passed
    assert any(i.code == "events_gt_total" for i in bad.issues)


def test_validate_extractions_routes_continuous():
    [res] = validate_extractions([_continuous_ext("ok", 10, 2, 50, 8, 2.5, 50)])
    assert res.passed


def test_continuous_rejects_zero_sd():
    [res] = validate_extractions([_continuous_ext("bad", 10, 0, 50, 8, 2.5, 50)])
    assert not res.passed
    assert any(i.code == "non_positive_sd" for i in res.issues)
