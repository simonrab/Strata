"""Pure-Python stats engine (no R required).

Pools per-study (yi, vi) effect points. tau^2 is estimated by REML via pymare
(a validated library). The inverse-variance weighting, Wald / HKSJ intervals, Q,
I^2 and the prediction interval follow the Cochrane Handbook v6.5 Chapter 10
formulas. Used when the metafor bridge is unavailable; cross-checked against
metafor in the test suite.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import stats

from ..schema import EffectPoint

_Z = 1.959963984540054  # qnorm(0.975)


def available() -> bool:
    return True


def _reml_tau2(yi: np.ndarray, vi: np.ndarray) -> float:
    from pymare import Dataset
    from pymare.estimators import VarianceBasedLikelihoodEstimator

    ds = Dataset(y=yi.reshape(-1, 1), v=vi.reshape(-1, 1))
    est = VarianceBasedLikelihoodEstimator(method="REML").fit_dataset(ds)
    return float(np.asarray(est.summary().tau2).ravel()[0])


def fit(points: Sequence[EffectPoint], method: str = "REML") -> dict:
    yi = np.asarray([p.yi for p in points], float)
    vi = np.asarray([p.vi for p in points], float)
    k = len(yi)
    tau2 = _reml_tau2(yi, vi) if method.upper() == "REML" else 0.0

    # Random-effects inverse-variance weights.
    w = 1.0 / (vi + tau2)
    beta = float(np.sum(w * yi) / np.sum(w))
    se_wald = float(np.sqrt(1.0 / np.sum(w)))

    # Cochran's Q from fixed-effect weights.
    wf = 1.0 / vi
    beta_fe = np.sum(wf * yi) / np.sum(wf)
    q = float(np.sum(wf * (yi - beta_fe) ** 2))
    df = k - 1
    q_p = float(stats.chi2.sf(q, df)) if df > 0 else 1.0

    # I^2 the metafor way: from the REML tau^2 and the "typical" within-study
    # variance (Higgins & Thompson 2002), not the Q-based estimator.
    s2 = df * np.sum(wf) / (np.sum(wf) ** 2 - np.sum(wf**2)) if df > 0 else 0.0
    i2 = float(100.0 * tau2 / (tau2 + s2)) if (tau2 + s2) > 0 else 0.0

    # HKSJ standard error (t-distribution, k-1 df).
    se_hksj = float(np.sqrt(np.sum(w * (yi - beta) ** 2) / (df * np.sum(w)))) if df > 0 else se_wald
    t_crit = stats.t.ppf(0.975, df) if df > 0 else _Z

    per_study = [
        {
            "study_id": p.study_id,
            "label": p.label,
            "yi": float(yi[i]),
            "vi": float(vi[i]),
            "weight": float(100.0 * w[i] / np.sum(w)),
        }
        for i, p in enumerate(points)
    ]

    # Prediction interval only when there are enough studies (>= 5).
    pred_lb = pred_ub = None
    if k >= 5:
        t_pred = stats.t.ppf(0.975, k - 2)
        spread = np.sqrt(tau2 + se_wald**2)
        pred_lb = float(beta - t_pred * spread)
        pred_ub = float(beta + t_pred * spread)

    return {
        "engine": "python",
        "k": k,
        "est_log": beta,
        "se_wald_log": se_wald,
        "se_hksj_log": se_hksj,
        "wald_lb_log": beta - _Z * se_wald,
        "wald_ub_log": beta + _Z * se_wald,
        "hksj_lb_log": beta - float(t_crit) * se_hksj,
        "hksj_ub_log": beta + float(t_crit) * se_hksj,
        "tau2": tau2,
        "i2": i2,
        "q": q,
        "q_p": q_p,
        "pred_lb_log": pred_lb,
        "pred_ub_log": pred_ub,
        "per_study": per_study,
    }
