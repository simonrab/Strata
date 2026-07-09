"""Stats engine dispatcher.

Prefers the metafor Rscript bridge (Cochrane-faithful reference implementation),
falls back to the pure-Python engine when R/metafor is unavailable. The
interval-selection rule lives here so both engines behave identically:

    HKSJ (t-distribution) when tau^2 > 0 and k > 2, otherwise Wald.

Never hand-rolls pooling — tau^2 comes from a validated estimator (metafor's
REML, or pymare's REML in the fallback).
"""

from __future__ import annotations

import math
import os
from collections.abc import Sequence

from ..schema import (
    RATIO_MEASURES,
    BinaryEffect,
    CIMethod,
    EffectMeasure,
    EffectPoint,
    PoolResult,
    StudyResult,
)
from . import escalc
from . import fallback as _python
from . import metafor as _metafor
from . import rare_event as _rare


def choose_ci_method(tau2: float, k: int) -> CIMethod:
    """Cochrane rule: HKSJ when there is heterogeneity and enough studies."""
    return CIMethod.HKSJ if (tau2 > 0 and k > 2) else CIMethod.WALD


def _select_engine() -> tuple[str, object]:
    pref = os.environ.get("LIVEMETA_STATS_ENGINE", "auto").lower()
    if pref in ("auto", "metafor") and _metafor.available():
        return "metafor", _metafor
    if pref == "metafor":
        raise RuntimeError("stats engine 'metafor' requested but R/metafor is unavailable")
    return "python", _python


def pool(
    studies: Sequence[BinaryEffect | EffectPoint],
    measure: EffectMeasure = EffectMeasure.RR,
    method: str = "REML",
) -> PoolResult:
    """Pool per-study effects into a random-effects estimate.

    Accepts either 2x2 binary tables (converted to effect points via Cochrane
    formulas) or pre-computed EffectPoints (e.g. log hazard ratios).
    """
    if len(studies) < 2:
        raise ValueError("pooling requires at least two studies")

    # Rare-event route: sparse 2x2 tables break inverse-variance, so pool them
    # with Peto rather than raising on the zero cell (Cochrane Handbook 10.4.4).
    binary = [s for s in studies if isinstance(s, BinaryEffect)]
    if measure in RATIO_MEASURES and len(binary) == len(studies) and _rare.is_rare(binary):
        return _rare.pool_peto(binary, measure=measure)

    points = [
        s if isinstance(s, EffectPoint) else escalc.binary_point(s, measure)
        for s in studies
    ]

    engine_name, backend = _select_engine()
    fit = backend.fit(points, method=method)
    result = _build_result(fit, measure=measure, method=method, engine=engine_name)
    # Surface every per-study data conversion (SE from CI, SMD Hedges' J, SD
    # recovery) on the pooled result so the audit trail can show them.
    result.assumptions = [a for p in points for a in p.assumptions]
    return result


def _build_result(fit: dict, *, measure: EffectMeasure, method: str, engine: str) -> PoolResult:
    k = fit["k"]
    tau2 = fit["tau2"]
    ci_method = choose_ci_method(tau2, k)

    if ci_method is CIMethod.HKSJ:
        lb_log, ub_log, se_log = fit["hksj_lb_log"], fit["hksj_ub_log"], fit["se_hksj_log"]
    else:
        lb_log, ub_log, se_log = fit["wald_lb_log"], fit["wald_ub_log"], fit["se_wald_log"]

    est_log = fit["est_log"]
    # Ratio measures pool on the log scale (exp back); MD/SMD are already natural.
    to_natural = math.exp if measure in RATIO_MEASURES else (lambda x: x)

    studies_out = [
        StudyResult(
            study_id=s["study_id"],
            label=s["label"],
            yi=s["yi"],
            vi=s["vi"],
            effect=to_natural(s["yi"]),
            ci_low=to_natural(s["yi"] - 1.959963984540054 * math.sqrt(s["vi"])),
            ci_high=to_natural(s["yi"] + 1.959963984540054 * math.sqrt(s["vi"])),
            weight=s["weight"],
        )
        for s in fit["per_study"]
    ]

    pred_low = pred_high = None
    if fit.get("pred_lb_log") is not None and fit.get("pred_ub_log") is not None:
        pred_low = to_natural(fit["pred_lb_log"])
        pred_high = to_natural(fit["pred_ub_log"])

    notes: list[str] = []
    if ci_method is CIMethod.HKSJ and k <= 3:
        notes.append("HKSJ interval can be too wide with only 2-3 studies.")
    if ci_method is CIMethod.WALD and tau2 > 0:
        notes.append("Wald interval used; can be too narrow with few studies.")

    return PoolResult(
        measure=measure,
        method=method,
        engine=engine,
        k=k,
        estimate=to_natural(est_log),
        ci_low=to_natural(lb_log),
        ci_high=to_natural(ub_log),
        ci_method=ci_method,
        estimate_log=est_log,
        se_log=se_log,
        ci_low_log=lb_log,
        ci_high_log=ub_log,
        tau2=tau2,
        i2=fit["i2"],
        q=fit["q"],
        q_p=fit["q_p"],
        prediction_low=pred_low,
        prediction_high=pred_high,
        studies=studies_out,
        notes=notes,
    )
