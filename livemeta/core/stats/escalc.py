"""Effect-size calculation — the per-study (yi, vi) points that get pooled.

These are standard Cochrane Handbook v6.5 transformations, run in code and
logged as assumptions. Effect-size calculation is *not* pooling: the weighted
average, tau^2 and intervals stay in the validated stats engine.
"""

from __future__ import annotations

import math

from ..schema import (
    Assumption,
    BinaryEffect,
    ContinuousEffect,
    EffectMeasure,
    EffectPoint,
    Provenance,
)

_Z = 1.959963984540054  # qnorm(0.975)


def binary_point(effect: BinaryEffect, measure: EffectMeasure) -> EffectPoint:
    """Log risk ratio or odds ratio and its variance from a 2x2 table."""
    a, n1 = effect.treatment.events, effect.treatment.total
    c, n2 = effect.control.events, effect.control.total
    b, d = n1 - a, n2 - c

    if measure is EffectMeasure.RR:
        if a == 0 or c == 0:
            raise ValueError(
                f"zero-cell in {effect.study_id}: route to rare-event handling (Peto/M-H)"
            )
        yi = math.log((a / n1) / (c / n2))
        vi = 1 / a - 1 / n1 + 1 / c - 1 / n2
    elif measure is EffectMeasure.OR:
        if a == 0 or b == 0 or c == 0 or d == 0:
            raise ValueError(
                f"zero-cell in {effect.study_id}: route to rare-event handling (Peto/M-H)"
            )
        yi = math.log((a * d) / (b * c))
        vi = 1 / a + 1 / b + 1 / c + 1 / d
    else:
        raise ValueError(f"binary_point does not support measure {measure}")

    return EffectPoint(
        study_id=effect.study_id,
        label=effect.label,
        yi=yi,
        vi=vi,
        provenance=effect.provenance,
    )


def continuous_point(effect: ContinuousEffect, measure: EffectMeasure) -> EffectPoint:
    """Mean difference or standardized mean difference from mean/SD/n per arm.

    Cochrane Handbook v6.5:
      MD  = m1 - m2,  var = sd1^2/n1 + sd2^2/n2.
      SMD = Hedges' g = Cohen's d * J, on the pooled within-group SD, where the
      small-sample correction J = 1 - 3/(4*(n1+n2) - 9);
      var(g) = (n1+n2)/(n1*n2) + g^2 / (2*(n1+n2)).
    SMD assumes approximate normality — check for skew upstream.
    """
    m1, sd1, n1 = effect.treatment.mean, effect.treatment.sd, effect.treatment.n
    m2, sd2, n2 = effect.control.mean, effect.control.sd, effect.control.n

    assumptions: list[Assumption] = []
    if measure is EffectMeasure.MD:
        yi = m1 - m2
        vi = sd1 * sd1 / n1 + sd2 * sd2 / n2
    elif measure is EffectMeasure.SMD:
        s_within = math.sqrt(
            ((n1 - 1) * sd1 * sd1 + (n2 - 1) * sd2 * sd2) / (n1 + n2 - 2)
        )
        d = (m1 - m2) / s_within
        j = 1.0 - 3.0 / (4.0 * (n1 + n2) - 9.0)  # Hedges' small-sample correction
        yi = d * j
        vi = (n1 + n2) / (n1 * n2) + yi * yi / (2.0 * (n1 + n2))
        assumptions.append(
            Assumption(
                code="smd_hedges_j",
                detail=(
                    f"SMD = Cohen's d × J with the Hedges small-sample correction "
                    f"J = 1 − 3/(4·{n1 + n2} − 9) = {j:.4f} (Cochrane Handbook 6.5.1.2)."
                ),
                study_id=effect.study_id,
            )
        )
    else:
        raise ValueError(f"continuous_point does not support measure {measure}")

    return EffectPoint(
        study_id=effect.study_id,
        label=effect.label,
        yi=yi,
        vi=vi,
        provenance=effect.provenance,
        assumptions=assumptions,
    )


def ratio_ci_point(
    study_id: str,
    label: str,
    ratio: float,
    ci_low: float,
    ci_high: float,
    provenance: list[Provenance] | None = None,
) -> EffectPoint:
    """Log effect and variance from a reported ratio (e.g. HR) and its 95% CI.

    Cochrane Handbook 6.5.2.3: SE(log ratio) = (log(upper) - log(lower)) / (2 * 1.96).
    """
    if ratio <= 0 or ci_low <= 0 or ci_high <= 0:
        raise ValueError(f"non-positive ratio/CI in {study_id}")
    yi = math.log(ratio)
    se = (math.log(ci_high) - math.log(ci_low)) / (2 * _Z)
    assumption = Assumption(
        code="log_ratio_se_from_ci",
        detail=(
            f"SE(ln ratio) = (ln {ci_high} − ln {ci_low}) / (2 × 1.95996) = {se:.4f} "
            f"(Cochrane Handbook 6.5.2.3)."
        ),
        study_id=study_id,
    )
    return EffectPoint(
        study_id=study_id,
        label=label,
        yi=yi,
        vi=se * se,
        provenance=provenance or [],
        assumptions=[assumption],
    )


def sd_from_se(se: float, n: int, study_id: str | None = None) -> tuple[float, Assumption]:
    """Recover a standard deviation from a reported standard error.

    SD = SE × sqrt(n) (Cochrane Handbook 6.5.2.2). Used when a trial reports an
    SE (or a CI, via `sd_from_ci`) for an arm mean instead of the SD the
    continuous effect-size formulas need. Returns the SD and the logged
    assumption so the caller can attach it to the extraction.
    """
    if se < 0 or n < 1:
        raise ValueError(f"invalid SE/n for SD recovery in {study_id}")
    sd = se * math.sqrt(n)
    assumption = Assumption(
        code="sd_from_se",
        detail=f"SD = SE × √n = {se} × √{n} = {sd:.4f} (Cochrane Handbook 6.5.2.2).",
        study_id=study_id,
    )
    return sd, assumption


def sd_from_ci(
    ci_low: float, ci_high: float, n: int, study_id: str | None = None
) -> tuple[float, Assumption]:
    """Recover a standard deviation from a 95% CI of an arm mean.

    SE = (upper − lower) / (2 × 1.96), then SD = SE × sqrt(n) (Cochrane Handbook
    6.5.2.2/6.5.2.3). Assumes the CI is a normal-approximation 95% interval.
    """
    if n < 1 or ci_high < ci_low:
        raise ValueError(f"invalid CI/n for SD recovery in {study_id}")
    se = (ci_high - ci_low) / (2 * _Z)
    sd = se * math.sqrt(n)
    assumption = Assumption(
        code="sd_from_ci",
        detail=(
            f"SE = ({ci_high} − {ci_low}) / (2 × 1.95996) = {se:.4f}; "
            f"SD = SE × √{n} = {sd:.4f} (Cochrane Handbook 6.5.2.2)."
        ),
        study_id=study_id,
    )
    return sd, assumption
