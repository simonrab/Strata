"""Effect-size calculation — the per-study (yi, vi) points that get pooled.

These are standard Cochrane Handbook v6.5 transformations, run in code and
logged as assumptions. Effect-size calculation is *not* pooling: the weighted
average, tau^2 and intervals stay in the validated stats engine.
"""

from __future__ import annotations

import math

from ..schema import BinaryEffect, EffectMeasure, EffectPoint, Provenance

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
    return EffectPoint(
        study_id=study_id,
        label=label,
        yi=yi,
        vi=se * se,
        provenance=provenance or [],
    )
