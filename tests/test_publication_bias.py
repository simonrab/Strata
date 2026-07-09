"""Funnel-plot asymmetry / Egger's small-study-effects test.

A deterministic quantitative check for publication bias, reusing each study's
(yi, vi). Per Cochrane it is only meaningful with at least 10 studies — below
that, `applicable` is False and GRADE keeps Claude's qualitative judgment.
"""

import math

import pytest

from livemeta.core.schema import EffectMeasure, EffectPoint, PoolResult, CIMethod
from livemeta.core.stats import engine as stats_engine
from livemeta.core.stats.publication_bias import egger_test, funnel_points


def _point(sid, yi, vi):
    return EffectPoint(study_id=sid, label=sid, yi=yi, vi=vi)


def _symmetric(n=12):
    # Balanced ± deviations at each variance level, so effect size is uncorrelated
    # with precision → a symmetric funnel and an Egger intercept of ~0.
    pts = []
    level = 0
    while len(pts) < n:
        vi = 0.02 + 0.03 * level
        pts.append(_point(f"S{len(pts)}", -0.15 + 0.05, vi))
        if len(pts) < n:
            pts.append(_point(f"S{len(pts)}", -0.15 - 0.05, vi))
        level += 1
    return pts


def test_not_applicable_below_10_studies():
    res = egger_test(_symmetric(9))
    assert res.applicable is False
    assert res.k == 9


def test_symmetric_funnel_has_near_zero_intercept():
    res = egger_test(_symmetric(12))
    assert res.applicable is True
    assert res.k == 12
    assert abs(res.intercept) < 0.5
    assert res.p > 0.10  # no significant small-study effect


def test_asymmetric_funnel_flags_small_study_effect():
    # Small studies (large vi) report systematically larger effects → asymmetry.
    pts = []
    for i in range(12):
        vi = 0.01 + 0.05 * i  # increasing variance
        yi = 0.10 + 2.5 * vi  # bigger effect in the less-precise studies
        pts.append(_point(f"S{i}", yi, vi))
    res = egger_test(pts)
    assert res.applicable is True
    assert res.p < 0.10
    assert res.intercept > 0


def test_funnel_points_shape():
    pool = _pool_from(_symmetric(10))
    pts = funnel_points(pool)
    assert len(pts) == 10
    p0 = pts[0]
    assert set(p0) >= {"study_id", "label", "effect", "se"}
    assert p0["se"] == pytest.approx(math.sqrt(pool.studies[0].vi))


def _pool_from(points) -> PoolResult:
    return stats_engine.pool(points, measure=EffectMeasure.HR)


def test_egger_result_serializes_on_pool_measure():
    # Sanity: the result carries k and the applicable flag for the UI.
    res = egger_test(_symmetric(11))
    dumped = res.model_dump()
    assert dumped["k"] == 11
    assert "applicable" in dumped and "intercept" in dumped
