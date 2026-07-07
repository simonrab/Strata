"""Deterministic validation gate.

Plain code — not the model — runs these checks before any pooling. Cochrane-
aligned: events cannot exceed arm totals, totals must be positive, counts must be
non-negative, and any reported percentage must match its count. Failures are
flagged for human review, never silently pooled.
"""

from __future__ import annotations

from collections.abc import Sequence

from .schema import (
    BinaryArm,
    BinaryEffect,
    TrialExtraction,
    ValidationIssue,
    ValidationResult,
)

# A reported percentage is a rounded figure; allow half a point of slack.
_PCT_TOLERANCE = 0.5


def _check_arm(study_id: str, arm: BinaryArm, which: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if arm.total <= 0:
        issues.append(
            ValidationIssue(
                study_id=study_id,
                code="non_positive_total",
                message=f"{which} arm total must be positive (got {arm.total}).",
            )
        )
    if arm.events < 0 or arm.total < 0:
        issues.append(
            ValidationIssue(
                study_id=study_id,
                code="negative_count",
                message=f"{which} arm has a negative count.",
            )
        )
    if arm.total > 0 and arm.events > arm.total:
        issues.append(
            ValidationIssue(
                study_id=study_id,
                code="events_gt_total",
                message=f"{which} arm events ({arm.events}) exceed total ({arm.total}).",
            )
        )
    if arm.reported_pct is not None and arm.total > 0:
        computed = 100.0 * arm.events / arm.total
        if abs(computed - arm.reported_pct) > _PCT_TOLERANCE:
            issues.append(
                ValidationIssue(
                    study_id=study_id,
                    code="pct_mismatch",
                    message=(
                        f"{which} arm reported {arm.reported_pct}% but "
                        f"{arm.events}/{arm.total} = {computed:.1f}%."
                    ),
                )
            )
    return issues


def validate_binary(effects: Sequence[BinaryEffect]) -> list[ValidationResult]:
    """Validate each binary effect; return one result per study."""
    results: list[ValidationResult] = []
    for e in effects:
        issues = _check_arm(e.study_id, e.treatment, "treatment") + _check_arm(
            e.study_id, e.control, "control"
        )
        results.append(
            ValidationResult(study_id=e.study_id, passed=not issues, issues=issues)
        )
    return results


def validate_ratio(extractions: Sequence[TrialExtraction]) -> list[ValidationResult]:
    """Deterministic gate for ratio-with-CI extractions (e.g. hazard ratios).

    A trial passes only if it was extracted (not flagged) and its confidence
    interval is positive and correctly ordered around the point estimate.
    """
    results: list[ValidationResult] = []
    for e in extractions:
        issues: list[ValidationIssue] = []
        if e.flagged or e.hr is None or e.ci_low is None or e.ci_high is None:
            issues.append(
                ValidationIssue(
                    study_id=e.study_id,
                    code="not_extracted",
                    message=e.flag_reason or "No usable effect estimate extracted.",
                )
            )
        else:
            if e.hr <= 0 or e.ci_low <= 0 or e.ci_high <= 0:
                issues.append(
                    ValidationIssue(
                        study_id=e.study_id,
                        code="non_positive_ratio",
                        message="Ratio and CI bounds must be positive.",
                    )
                )
            if not (e.ci_low <= e.hr <= e.ci_high):
                issues.append(
                    ValidationIssue(
                        study_id=e.study_id,
                        code="ci_not_ordered",
                        message=f"CI {e.ci_low}-{e.ci_high} does not bracket HR {e.hr}.",
                    )
                )
        results.append(
            ValidationResult(study_id=e.study_id, passed=not issues, issues=issues)
        )
    return results
