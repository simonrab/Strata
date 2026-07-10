"""Build a PRISMA 2020 record-flow from a completed review — plain code, no model.

The PRISMA flow diagram is the systematic-review artifact that makes a synthesis
reproducible: it accounts for every record from the search down to the studies
pooled, with reasons for each exclusion. This module derives that flow purely
from what the pipeline already recorded — the candidate ids, the extractions,
the validations, and the pool — so the counts can never drift from the run.

Deliberately honest: the pipeline identifies trials by search, de-duplicates,
retrieves, screens each candidate for clinical eligibility against the question's
PICO (the `screen` module), and then requires extractable effect data plus the
deterministic validation gate. Every exclusion reason in the funnel is a real one
the pipeline produced — an ineligible population/intervention/comparator or study
design from the screen, or (further down) no extractable effect data, incomplete
data, failed validation, or a reviewer's flag. The funnel is internally
consistent by construction (see PrismaFlow).
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence

from .schema import (
    PrismaExclusion,
    PrismaFlow,
    ReviewResult,
    TrialExtraction,
    ValidationResult,
)

# Validation issue code -> the eligibility-exclusion reason shown in the flow.
_VALIDATION_LABELS = {
    "events_gt_total": "Events exceed arm total",
    "pct_mismatch": "Reported percentage inconsistent with counts",
    "ci_not_ordered": "Confidence interval does not bracket the estimate",
    "non_positive_ratio": "Non-positive ratio or CI bound",
    "implausible_ratio": "Effect ratio outside the plausible range",
    "implausible_ci_width": "Confidence interval implausibly wide",
    "non_positive_total": "Invalid arm total",
    "negative_count": "Negative event count",
    "non_positive_sd": "Non-positive standard deviation",
    "non_positive_n": "Invalid arm size",
    "non_finite_mean": "Non-finite mean",
}


def dedupe_preserving_order(trial_ids: Sequence[str]) -> list[str]:
    """The unique trial ids in first-seen order — the PRISMA de-duplication step.

    Shared by the pipeline (which screens/pools the unique set) and this builder
    (which counts `duplicates_removed`), so the funnel and the run can never
    disagree on what was de-duplicated.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for tid in trial_ids:
        if tid not in seen:
            seen.add(tid)
            unique.append(tid)
    return unique


def _source_of(trial_id: str) -> str:
    """Best-effort display bucket for where a record id came from."""
    t = (trial_id or "").upper()
    if t.startswith("NCT"):
        return "ClinicalTrials.gov"
    if t.startswith(("PMC", "MED", "PMID")) or t.replace("PMID:", "").isdigit():
        return "Europe PMC"
    return "Other"


def _is_not_retrieved(reason: str | None) -> bool:
    """A screening-stage drop: the report was sought but could not be retrieved."""
    return "could not retrieve" in (reason or "").lower()


def _flag_bucket(reason: str | None) -> str:
    """Map a (non-retrieval) flagged-extraction reason to an eligibility bucket.

    Falls back to the raw reason so a reviewer's own flag text stays visible and
    groups on itself rather than a generic label.
    """
    r = (reason or "").lower()
    if "requires the model" in r or "model read" in r or "model call failed" in r:
        return "Automated text extraction unavailable"
    if "low-confidence" in r or "manual review" in r:
        return "Low-confidence read — routed to manual review"
    if "incomplete" in r or "inconsistent" in r:
        return "Reported effect data incomplete"
    if (
        "no hazard-ratio" in r
        or "no structured" in r
        or "not clearly reported" in r
        or "does not report a standard deviation" in r
    ):
        return "No extractable effect data reported"
    return (reason or "").strip() or "Excluded on review"


def _validation_bucket(issues: Sequence) -> str:
    for issue in issues:
        label = _VALIDATION_LABELS.get(getattr(issue, "code", ""))
        if label:
            return label
    return "Failed validation"


# Eligibility-screen exclusion, bucketed by the PICO domain that failed so the
# funnel groups like reasons (the per-trial rationale lives in the screening
# ledger, `ReviewResult.screening`).
_SCREEN_LABELS = {
    "population": "Ineligible population",
    "intervention": "Ineligible intervention",
    "comparator": "Ineligible comparator",
    "outcome": "Ineligible outcome",
    "design": "Ineligible study design",
}


def _screen_bucket(decision) -> str:
    return _SCREEN_LABELS.get(decision.domain or "", "Excluded at eligibility screening")


def build_prisma(result: ReviewResult) -> PrismaFlow:
    """Derive the PRISMA 2020 flow for one review run.

    Every record in `question.trial_ids` lands in exactly one terminal bucket —
    a duplicate, a not-retrieved report, an eligibility exclusion, or an included
    study — so the stage counts always reconcile.
    """
    trial_ids = list(result.question.trial_ids)
    identified = len(trial_ids)

    by_source: "OrderedDict[str, int]" = OrderedDict()
    for tid in trial_ids:
        src = _source_of(tid)
        by_source[src] = by_source.get(src, 0) + 1

    # De-duplicate, preserving first-seen order (the shared PRISMA screen step).
    unique_ids = dedupe_preserving_order(trial_ids)
    duplicates_removed = identified - len(unique_ids)
    screened = len(unique_ids)

    ext_by_id: dict[str, TrialExtraction] = {e.study_id: e for e in result.extractions}
    val_by_id: dict[str, ValidationResult] = {v.study_id: v for v in result.validations}
    passed_ids = {v.study_id for v in result.validations if v.passed}
    screen_by_id = {d.study_id: d for d in result.screening}

    not_retrieved = 0
    included = 0
    buckets: "OrderedDict[str, list[str]]" = OrderedDict()
    bucket_stage: dict[str, str] = {}

    def _exclude(label: str, sid: str, stage: str) -> None:
        buckets.setdefault(label, []).append(sid)
        bucket_stage.setdefault(label, stage)

    for tid in unique_ids:
        # A clinical eligibility exclusion is decided before extraction, so it has
        # no extraction record — classify it first, distinct from a not-retrieved
        # report, so the funnel shows a real screening stage with clinical reasons.
        decision = screen_by_id.get(tid)
        if decision is not None and decision.decision == "excluded":
            _exclude(_screen_bucket(decision), tid, "screening")
            continue
        ext = ext_by_id.get(tid)
        if ext is None:
            # No extraction record at all — treat as a report that never arrived.
            not_retrieved += 1
            continue
        if ext.flagged:
            if _is_not_retrieved(ext.flag_reason):
                not_retrieved += 1
            else:
                _exclude(_flag_bucket(ext.flag_reason), tid, "reports")
            continue
        if tid in passed_ids:
            included += 1
        else:
            val = val_by_id.get(tid)
            _exclude(_validation_bucket(val.issues if val else []), tid, "reports")

    excluded = [
        PrismaExclusion(
            reason=label, count=len(ids), study_ids=ids, stage=bucket_stage[label]
        )
        for label, ids in buckets.items()
    ]
    assessed = screened - not_retrieved

    pool = result.pool
    included_in_synthesis = pool.k if pool is not None else 0
    synthesis_note = ""
    if pool is None:
        div = result.diversity
        if div is not None and div.requires_confirmation and not div.confirmed:
            synthesis_note = "Pooling withheld pending homogeneity confirmation."
        elif included < 2:
            synthesis_note = "Too few eligible studies to pool — abstained."
        else:
            synthesis_note = "Eligible studies not pooled."

    return PrismaFlow(
        identified=identified,
        identified_by_source=dict(by_source),
        duplicates_removed=duplicates_removed,
        screened=screened,
        not_retrieved=not_retrieved,
        assessed=assessed,
        excluded=excluded,
        included=included,
        included_in_synthesis=included_in_synthesis,
        synthesis_note=synthesis_note,
    )
