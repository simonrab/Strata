"""Stats engine — the trust story. Pooled numbers must match metafor exactly.

Ground truth was computed with R metafor:
  escalc(measure="RR", ...); rma(yi, vi, method="REML", test="z" | "knha")
and enshrined here as expected values (see scratchpad ref.R / ref2.R).

The engine must:
  * pool ratio measures on the log scale,
  * estimate tau^2 with REML,
  * select the HKSJ (knha) interval when tau^2 > 0 and k > 2, else Wald,
  * agree across the metafor bridge and the pure-Python fallback.
"""

import math

import pytest

from livemeta.core.schema import BinaryArm, BinaryEffect, CIMethod, EffectMeasure
from livemeta.core.stats import engine as stats_engine
from livemeta.core.stats import escalc
from livemeta.core.stats import metafor as metafor_engine


def _studies(rows):
    return [
        BinaryEffect(
            study_id=f"S{i+1}",
            label=f"Study {i+1}",
            treatment=BinaryArm(events=et, total=nt),
            control=BinaryArm(events=ec, total=nc),
        )
        for i, (et, nt, ec, nc) in enumerate(rows)
    ]


# Fixture A — homogeneous (tau^2 == 0 -> Wald interval expected)
HOMOGENEOUS = _studies(
    [(100, 1000, 120, 1000), (50, 500, 65, 500), (30, 400, 40, 400),
     (200, 2000, 240, 2000), (15, 300, 25, 300)]
)
EXPECT_A = {
    "estimate_log": -0.2142960616,
    "ci_low_log": -0.3396963719,   # Wald
    "ci_high_log": -0.0888957512,  # Wald
    "tau2": 0.0,
    "i2": 0.0,
    "q": 1.2416786478,
    "ci_method": CIMethod.WALD,
}

# Fixture B — heterogeneous (tau^2 > 0, k=5 -> HKSJ interval expected)
HETEROGENEOUS = _studies(
    [(50, 500, 100, 500), (90, 500, 100, 500), (120, 500, 100, 500),
     (70, 500, 100, 500), (110, 500, 100, 500)]
)
EXPECT_B = {
    "estimate_log": -0.1647431185,
    "ci_low_log": -0.6023598020,   # HKSJ (knha)
    "ci_high_log": 0.2728735649,   # HKSJ (knha)
    "tau2": 0.1034257518,
    "i2": 85.2468795619,
    "q": 24.8347122987,
    "ci_method": CIMethod.HKSJ,
}

ENGINES = ["python"]
if metafor_engine.available():
    ENGINES.append("metafor")


@pytest.fixture(params=ENGINES)
def engine_env(request, monkeypatch):
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", request.param)
    return request.param


@pytest.mark.parametrize(
    "studies,expected",
    [(HOMOGENEOUS, EXPECT_A), (HETEROGENEOUS, EXPECT_B)],
    ids=["homogeneous-wald", "heterogeneous-hksj"],
)
def test_pool_matches_metafor(engine_env, studies, expected):
    res = stats_engine.pool(studies, measure=EffectMeasure.RR)

    assert res.k == 5
    assert res.ci_method == expected["ci_method"]
    assert res.estimate_log == pytest.approx(expected["estimate_log"], abs=1e-4)
    assert res.ci_low_log == pytest.approx(expected["ci_low_log"], abs=1e-4)
    assert res.ci_high_log == pytest.approx(expected["ci_high_log"], abs=1e-4)
    assert res.tau2 == pytest.approx(expected["tau2"], abs=1e-4)
    assert res.i2 == pytest.approx(expected["i2"], abs=1e-2)
    assert res.q == pytest.approx(expected["q"], abs=1e-3)

    # Natural-scale estimate is exp() of the log estimate for ratio measures.
    assert res.estimate == pytest.approx(math.exp(expected["estimate_log"]), abs=1e-4)
    assert res.ci_low == pytest.approx(math.exp(expected["ci_low_log"]), abs=1e-4)


def test_per_study_weights_sum_to_100(engine_env):
    res = stats_engine.pool(HETEROGENEOUS, measure=EffectMeasure.RR)
    assert len(res.studies) == 5
    assert sum(s.weight for s in res.studies) == pytest.approx(100.0, abs=1e-6)
    # Each study carries its own log effect and natural-scale RR.
    for s in res.studies:
        assert s.effect == pytest.approx(math.exp(s.yi), abs=1e-9)


def test_prediction_interval_present_for_five_studies(engine_env):
    res = stats_engine.pool(HETEROGENEOUS, measure=EffectMeasure.RR)
    assert res.prediction_low is not None and res.prediction_high is not None
    assert res.prediction_low < res.estimate < res.prediction_high


# --- Hazard-ratio pooling: the locked demo question ------------------------
# 8 GLP-1 RA cardiovascular outcome trials, 3-point MACE, as pooled by
# Sattar et al. Lancet Diabetes Endocrinol 2021 -> HR 0.86 (0.80-0.93).
GLP1_CVOTS = [
    # (trial, HR, ci_low, ci_high)
    ("ELIXA", 1.02, 0.89, 1.17),
    ("LEADER", 0.87, 0.78, 0.97),
    ("SUSTAIN-6", 0.74, 0.58, 0.95),
    ("EXSCEL", 0.91, 0.83, 1.00),
    ("Harmony", 0.78, 0.68, 0.90),
    ("REWIND", 0.88, 0.79, 0.99),
    ("PIONEER-6", 0.79, 0.57, 1.11),
    ("AMPLITUDE-O", 0.73, 0.58, 0.92),
]


def _glp1_points():
    return [
        escalc.ratio_ci_point(t, t, hr, lb, ub) for (t, hr, lb, ub) in GLP1_CVOTS
    ]


def test_pool_glp1_mace_matches_published(engine_env):
    res = stats_engine.pool(_glp1_points(), measure=EffectMeasure.HR)

    assert res.k == 8
    # Point estimate matches metafor / the published pooled HR of 0.86.
    assert res.estimate == pytest.approx(0.8621, abs=1e-3)
    assert res.estimate_log == pytest.approx(-0.1484334698, abs=1e-4)
    # Moderate heterogeneity, tau^2 > 0 with 8 studies -> HKSJ interval.
    assert res.ci_method == CIMethod.HKSJ
    assert res.i2 == pytest.approx(47.15, abs=0.1)
    # Rounds to the established answer band.
    assert round(res.estimate, 2) == 0.86
    assert res.ci_high < 1.0  # a statistically significant cardiovascular benefit
