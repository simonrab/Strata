"""The forward milestone radar: readouts and decisions still to come.

The one forward-looking lens. Every other view is present-or-past tense; this one
reads each trial's *primary completion date* (already parsed onto `TrialDetail`)
and surfaces the ones dated in the future that have not yet reported — bucketed by
quarter. Deterministic and offline: no model, just structured CT.gov dates.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .ctgov_pipeline import HALTED_STATUSES, study_to_trial_detail
from .schema import Milestone, MilestoneKind, MilestoneRadar, TrialDetail


def _today() -> str:
    return date.today().isoformat()


def _horizon_cutoff(as_of: str, horizon_months: int) -> str:
    """The ISO date `horizon_months` after `as_of` (month arithmetic, day held)."""
    year, month, day = (int(p) for p in as_of[:10].split("-"))
    total = (year * 12 + (month - 1)) + horizon_months
    ny, nm = divmod(total, 12)
    return f"{ny:04d}-{nm + 1:02d}-{day:02d}"


def _quarter(iso_date: str) -> str:
    year, month = int(iso_date[:4]), int(iso_date[5:7])
    return f"{year}-Q{(month - 1) // 3 + 1}"


def _milestone(trial: TrialDetail) -> Milestone:
    return Milestone(
        asset_name=trial.asset_name,
        indication=trial.indication,
        nct_id=trial.nct_id,
        title=trial.title,
        phase=trial.phase,
        kind=MilestoneKind.EXPECTED_READOUT,
        expected_date=trial.primary_completion_date or "",
        quarter=_quarter(trial.primary_completion_date or ""),
        sponsor=trial.sponsor,
        provenance=list(trial.provenance),
    )


def milestone_radar(
    store,
    scope: str,
    *,
    search: Callable[[str], list[dict]] | None = None,
    horizon_months: int = 18,
    as_of: str | None = None,
) -> MilestoneRadar:
    """Upcoming expected readouts for a condition (or sponsor), bucketed by quarter.

    A trial qualifies when its primary completion is in the future (relative to
    `as_of`/today), within the horizon, and it has not already posted results —
    i.e. a genuine forward milestone, not a trial that has already read out.
    """
    today = (as_of or _today())[:10]
    cutoff = _horizon_cutoff(today, horizon_months)
    notes: list[str] = []

    try:
        studies = search(scope) if search is not None else []
    except Exception:
        studies = []
        notes.append("Live ClinicalTrials.gov lookup was unavailable; radar may be incomplete.")

    milestones: list[Milestone] = []
    for study in studies:
        trial = study_to_trial_detail(study)
        # A halted trial won't read out, even with a future completion date.
        if (trial.status or "").upper() in HALTED_STATUSES:
            continue
        pcd = trial.primary_completion_date
        if not pcd or trial.has_results:
            continue
        if pcd <= today or pcd > cutoff:
            continue
        milestones.append(_milestone(trial))

    milestones.sort(key=lambda m: (m.expected_date, m.asset_name))

    return MilestoneRadar(
        scope=scope,
        as_of=today,
        horizon_months=horizon_months,
        milestones=milestones,
        notes=notes,
    )
