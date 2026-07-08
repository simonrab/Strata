"""Diff two review snapshots for the living layer.

The question the diff answers is not just "did the number move" but "did the
conclusion change" — i.e. did the statistical significance flip (the CI crossing
1) or did the direction of effect flip (the estimate crossing 1). Significance
and direction are read through the same helpers the summary uses
(`pipeline.pool_significant`, `pipeline.pool_direction`) so the two can never
disagree.
"""

from __future__ import annotations

from .pipeline import pool_direction, pool_significant
from .schema import PoolResult, ReviewDiff, ReviewResult

# A move smaller than this (relative to the previous estimate) is treated as
# engine noise rather than a real shift, so identical re-runs read "unchanged".
_REL_EPSILON = 0.005


def _ci(pool: PoolResult | None) -> tuple[float, float] | None:
    return (pool.ci_low, pool.ci_high) if pool else None


def status_from_diff(diff: ReviewDiff, *, rel_epsilon: float = _REL_EPSILON) -> str:
    """Map a diff to the dashboard's three-state status.

    Conclusion dominates: a flip in statistical significance or direction of
    effect is "conclusion-moved". Otherwise a real (non-noise) move in the point
    estimate is "estimate-updated"; anything smaller is "unchanged". Returns one
    of: "unchanged" | "estimate-updated" | "conclusion-moved".
    """
    if diff.conclusion_changed:
        return "conclusion-moved"
    if (
        diff.delta is not None
        and diff.estimate_prev
        and abs(diff.delta) / abs(diff.estimate_prev) >= rel_epsilon
    ):
        return "estimate-updated"
    return "unchanged"


def diff_reviews(
    previous: ReviewResult,
    current: ReviewResult,
    *,
    previous_version: int,
    current_version: int,
) -> ReviewDiff:
    prev_pool, curr_pool = previous.pool, current.pool

    est_prev = prev_pool.estimate if prev_pool else None
    est_curr = curr_pool.estimate if curr_pool else None
    delta = (est_curr - est_prev) if (est_prev is not None and est_curr is not None) else None

    added = [t for t in current.question.trial_ids if t not in set(previous.question.trial_ids)]

    notes: list[str] = []
    significance_changed = False
    direction_changed = False

    if prev_pool is None or curr_pool is None:
        # Abstention on either side is itself a conclusion change worth flagging.
        if prev_pool is None and curr_pool is not None:
            notes.append("Previous run abstained; the updated run produced a pooled estimate.")
            significance_changed = True
        elif prev_pool is not None and curr_pool is None:
            notes.append("Updated run abstained (too few valid trials or high heterogeneity).")
            significance_changed = True
    else:
        significance_changed = pool_significant(prev_pool) != pool_significant(curr_pool)
        direction_changed = pool_direction(prev_pool) != pool_direction(curr_pool)
        if significance_changed:
            was = "significant" if pool_significant(prev_pool) else "not significant"
            now = "significant" if pool_significant(curr_pool) else "not significant"
            notes.append(f"Statistical significance changed: {was} -> {now}.")
        if direction_changed:
            notes.append(
                f"Direction of effect changed: {pool_direction(prev_pool)} -> "
                f"{pool_direction(curr_pool)}."
            )

    conclusion_changed = significance_changed or direction_changed

    return ReviewDiff(
        question_id=current.question.id,
        previous_version=previous_version,
        current_version=current_version,
        estimate_prev=est_prev,
        estimate_curr=est_curr,
        delta=delta,
        ci_prev=_ci(prev_pool),
        ci_curr=_ci(curr_pool),
        k_prev=prev_pool.k if prev_pool else 0,
        k_curr=curr_pool.k if curr_pool else 0,
        added_trials=added,
        significance_changed=significance_changed,
        direction_changed=direction_changed,
        conclusion_changed=conclusion_changed,
        notes=notes,
    )
