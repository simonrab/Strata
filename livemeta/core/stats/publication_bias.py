"""Publication-bias detection: funnel-plot asymmetry via Egger's test.

Deterministic small-study-effects analysis, reusing each study's (yi, vi). Egger
regresses the standard normal deviate (yi/se) on precision (1/se); the intercept
measures funnel asymmetry, tested with a t-distribution (df = k - 2). Cochrane
Handbook 13.3.5.3: the test is underpowered and unreliable with fewer than 10
studies, so `applicable` is gated at k >= 10 — below that, GRADE keeps Claude's
qualitative judgment rather than a noisy statistic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..schema import EggerResult, PoolResult

_MIN_STUDIES = 10


def egger_test(studies: Sequence) -> EggerResult:
    """Egger's linear-regression test for funnel-plot asymmetry.

    Accepts anything carrying `yi` and `vi` (an EffectPoint or a StudyResult).
    Runs an unweighted OLS of SND = yi/se on precision = 1/se; the intercept and
    its t-test are the small-study-effects signal.
    """
    k = len(studies)
    if k < _MIN_STUDIES:
        return EggerResult(k=k, applicable=False)

    # SND_i = a + b * precision_i + e_i, with precision_i = 1/se_i.
    xs, ys = [], []
    for s in studies:
        se = math.sqrt(s.vi)
        if se <= 0:
            return EggerResult(k=k, applicable=False)
        xs.append(1.0 / se)
        ys.append(s.yi / se)

    n = float(k)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    if sxx == 0:
        return EggerResult(k=k, applicable=False)

    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    # Residual variance and the standard error of the intercept.
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    df = k - 2
    s2 = sum(r * r for r in residuals) / df
    se_intercept = math.sqrt(s2 * (1.0 / n + mean_x * mean_x / sxx))
    if se_intercept == 0:
        return EggerResult(k=k, intercept=intercept, se_intercept=0.0, applicable=True, p=1.0, t=0.0)

    t = intercept / se_intercept
    p = _two_sided_t_p(t, df)
    return EggerResult(
        k=k,
        intercept=intercept,
        se_intercept=se_intercept,
        t=t,
        p=p,
        applicable=True,
    )


def _two_sided_t_p(t: float, df: int) -> float:
    """Two-sided p-value for a t statistic (SciPy when available, else a fallback)."""
    try:
        from scipy import stats

        return float(2.0 * stats.t.sf(abs(t), df))
    except Exception:  # pragma: no cover - scipy is a declared dependency
        # Normal approximation fallback.
        return math.erfc(abs(t) / math.sqrt(2.0))


def funnel_points(pool: PoolResult) -> list[dict]:
    """Per-study points for a funnel plot: natural-scale effect and its SE."""
    return [
        {
            "study_id": s.study_id,
            "label": s.label,
            "effect": s.effect,
            "se": math.sqrt(s.vi),
        }
        for s in pool.studies
    ]
