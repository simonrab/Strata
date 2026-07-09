"""Data-conversion assumptions ledger.

Every Cochrane conversion the code runs (SE from a CI, Hedges' small-sample
correction, SD from SE/CI) is recorded as a machine-readable `Assumption` so the
audit trail can show exactly which formula produced each pooled number. The
conversions themselves are unchanged — this only makes them visible.
"""

import math

import pytest

from livemeta.core.schema import (
    Assumption,
    ContinuousArm,
    ContinuousEffect,
    EffectMeasure,
)
from livemeta.core.stats import escalc


def test_ratio_ci_point_logs_se_from_ci():
    point = escalc.ratio_ci_point("S1", "S1", 0.86, 0.79, 0.94)
    assert isinstance(point.assumptions, list)
    codes = [a.code for a in point.assumptions]
    assert "log_ratio_se_from_ci" in codes
    a = next(a for a in point.assumptions if a.code == "log_ratio_se_from_ci")
    assert a.study_id == "S1"
    assert isinstance(a, Assumption)
    assert a.detail  # human-readable, references the CI it was derived from


def test_mean_difference_logs_no_conversion():
    # A plain mean difference needs no conversion — nothing to log.
    eff = ContinuousEffect(
        study_id="S",
        label="S",
        treatment=ContinuousArm(mean=10, sd=2, n=50),
        control=ContinuousArm(mean=8, sd=2.5, n=50),
    )
    point = escalc.continuous_point(eff, EffectMeasure.MD)
    assert [a.code for a in point.assumptions] == []


def test_smd_logs_hedges_correction():
    eff = ContinuousEffect(
        study_id="S",
        label="S",
        treatment=ContinuousArm(mean=10, sd=2, n=50),
        control=ContinuousArm(mean=8, sd=2.5, n=50),
    )
    point = escalc.continuous_point(eff, EffectMeasure.SMD)
    assert "smd_hedges_j" in [a.code for a in point.assumptions]
    # The conversion itself is unchanged.
    assert point.yi == pytest.approx(0.876674, abs=1e-4)


def test_sd_from_se_conversion_and_logging():
    # SD = SE * sqrt(n) (Cochrane Handbook 6.5.2.2).
    sd, assumption = escalc.sd_from_se(se=0.5, n=64, study_id="S1")
    assert sd == pytest.approx(0.5 * math.sqrt(64))
    assert assumption.code == "sd_from_se"
    assert assumption.study_id == "S1"


def test_sd_from_ci_conversion_and_logging():
    # SD from a 95% CI of a mean: SE = (upper-lower)/(2*1.96), SD = SE*sqrt(n).
    sd, assumption = escalc.sd_from_ci(ci_low=8.0, ci_high=12.0, n=64, study_id="S1")
    expected_se = (12.0 - 8.0) / (2 * 1.959963984540054)
    assert sd == pytest.approx(expected_se * math.sqrt(64))
    assert assumption.code == "sd_from_ci"
