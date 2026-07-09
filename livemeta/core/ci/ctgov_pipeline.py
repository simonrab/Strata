"""Turn a ClinicalTrials.gov v2 record into competitive-pipeline events.

Purely deterministic — sponsor, phase, status, dates, interventions, and
condition all come straight from structured fields the tool already fetches.
Each derived event/asset carries provenance back to the trial. No inference
beyond direct field reads (the "no silent back-calculation" contract).
"""

from __future__ import annotations

from ..schema import Provenance
from .schema import (
    Asset,
    DevelopmentEvent,
    EventType,
    Phase,
    SourceType,
    TrialDetail,
)

# CT.gov `designModule.phases` (a list) → our single ordered Phase.
_PHASE_MAP: dict[frozenset[str], Phase] = {
    frozenset({"EARLY_PHASE1"}): Phase.PHASE_1,
    frozenset({"PHASE1"}): Phase.PHASE_1,
    frozenset({"PHASE1", "PHASE2"}): Phase.PHASE_1_2,
    frozenset({"PHASE2"}): Phase.PHASE_2,
    frozenset({"PHASE2", "PHASE3"}): Phase.PHASE_2_3,
    frozenset({"PHASE3"}): Phase.PHASE_3,
    frozenset({"PHASE4"}): Phase.PHASE_4,
}

# Statuses that mean the trial has read out (so a READOUT event is warranted).
_COMPLETED_STATUSES = {"COMPLETED", "TERMINATED"}

# Intervention arms that are not the asset under study.
_NON_ASSET_NAMES = {"placebo", "standard of care", "control", "sham", "best supportive care"}


def _protocol(study: dict) -> dict:
    return study.get("protocolSection", {})


def _nct(study: dict) -> str:
    return _protocol(study).get("identificationModule", {}).get("nctId", "UNKNOWN")


def _phase(study: dict) -> Phase:
    phases = _protocol(study).get("designModule", {}).get("phases", []) or []
    key = frozenset(p.upper() for p in phases if p and p.upper() != "NA")
    return _PHASE_MAP.get(key, Phase.UNKNOWN)


def _condition(study: dict) -> str:
    conditions = _protocol(study).get("conditionsModule", {}).get("conditions", []) or []
    return conditions[0] if conditions else "Unspecified"


def _sponsor(study: dict) -> tuple[str | None, str | None]:
    lead = _protocol(study).get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    return lead.get("name"), lead.get("class")


def _asset_name(study: dict) -> str | None:
    """The first drug/biologic arm that is not a placebo/control."""
    interventions = (
        _protocol(study).get("armsInterventionsModule", {}).get("interventions", []) or []
    )
    for iv in interventions:
        name = (iv.get("name") or "").strip()
        if not name:
            continue
        if (iv.get("type") or "").upper() not in ("DRUG", "BIOLOGICAL", "GENETIC", ""):
            continue
        if name.lower() in _NON_ASSET_NAMES:
            continue
        return name
    return None


def _norm_date(struct: dict | None) -> str | None:
    """Normalize a CT.gov dateStruct to a sortable ISO date, or None.

    CT.gov reports "YYYY-MM" or "YYYY-MM-DD"; pad the month form to the 1st so
    string comparison and the as-of filter order correctly.
    """
    if not struct:
        return None
    raw = (struct.get("date") or "").strip()
    if not raw:
        return None
    parts = raw.split("-")
    if len(parts) == 1:
        return f"{parts[0]}-01-01"
    if len(parts) == 2:
        return f"{parts[0]}-{parts[1]}-01"
    return raw


def study_to_asset(study: dict) -> Asset:
    nct = _nct(study)
    name = _asset_name(study) or _protocol(study).get("identificationModule", {}).get(
        "briefTitle", nct
    )
    sponsor, sponsor_class = _sponsor(study)
    prov = [
        Provenance(
            trial_id=nct,
            snippet=f"{name} — sponsor {sponsor or 'unknown'} ({sponsor_class or 'n/a'})",
            source_url=f"https://clinicaltrials.gov/study/{nct}",
            field="armsInterventionsModule.interventions / sponsorCollaboratorsModule",
        )
    ]
    return Asset(
        name=name,
        sponsor=sponsor,
        sponsor_class=sponsor_class,
        provenance=prov,
    )


def study_to_events(study: dict) -> list[DevelopmentEvent]:
    """Emit the dated pipeline milestones for one trial.

    A TRIAL_START event places the asset at its phase from the trial's start
    date; a READOUT event marks the primary-completion date when the trial has
    completed. Both are what let the landscape reconstruct the pipeline over time.
    """
    nct = _nct(study)
    status_mod = _protocol(study).get("statusModule", {})
    overall = status_mod.get("overallStatus")
    phase = _phase(study)
    indication = _condition(study)
    asset = _asset_name(study) or nct
    sponsor, sponsor_class = _sponsor(study)
    source_url = f"https://clinicaltrials.gov/study/{nct}"

    def _event(event_type: EventType, date: str | None, note: str) -> DevelopmentEvent:
        return DevelopmentEvent(
            asset_name=asset,
            indication=indication,
            phase=phase,
            status=overall,
            event_type=event_type,
            date=date,
            source_type=SourceType.CTGOV,
            sponsor=sponsor,
            sponsor_class=sponsor_class,
            provenance=[
                Provenance(
                    trial_id=nct, snippet=note, source_url=source_url, field="statusModule"
                )
            ],
        )

    events: list[DevelopmentEvent] = []
    start = _norm_date(status_mod.get("startDateStruct"))
    events.append(
        _event(
            EventType.TRIAL_START,
            start,
            f"{asset} entered {phase.value} for {indication} ({overall or 'status unknown'})",
        )
    )

    primary_completion = _norm_date(status_mod.get("primaryCompletionDateStruct"))
    if overall in _COMPLETED_STATUSES and primary_completion:
        events.append(
            _event(
                EventType.READOUT,
                primary_completion,
                f"{asset} {phase.value} trial for {indication} read out ({overall})",
            )
        )
    return events


def _countries(study: dict) -> list[str]:
    locations = (
        _protocol(study).get("contactsLocationsModule", {}).get("locations", []) or []
    )
    seen: list[str] = []
    for loc in locations:
        country = (loc.get("country") or "").strip()
        if country and country not in seen:
            seen.append(country)
    return seen


def _enrollment(study: dict) -> int | None:
    info = _protocol(study).get("designModule", {}).get("enrollmentInfo", {})
    value = info.get("count")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def study_to_trial_detail(study: dict) -> TrialDetail:
    """Deterministic map from a CT.gov v2 record to the enriched TrialDetail.

    Adds geography (countries), enrolment, and readout status/date on top of the
    phase/status/dates/sponsor the events parser already reads. Sub-population and
    the headline effect are attached later (Claude / results extraction).
    """
    nct = _nct(study)
    ident = _protocol(study).get("identificationModule", {})
    status_mod = _protocol(study).get("statusModule", {})
    sponsor, sponsor_class = _sponsor(study)
    results_posted = _norm_date(status_mod.get("resultsFirstPostDateStruct"))
    has_results = bool(study.get("hasResults")) or results_posted is not None

    return TrialDetail(
        nct_id=nct,
        title=ident.get("briefTitle") or ident.get("officialTitle") or nct,
        asset_name=_asset_name(study) or nct,
        phase=_phase(study),
        status=status_mod.get("overallStatus"),
        enrollment=_enrollment(study),
        start_date=_norm_date(status_mod.get("startDateStruct")),
        primary_completion_date=_norm_date(status_mod.get("primaryCompletionDateStruct")),
        results_posted_date=results_posted,
        has_results=has_results,
        sponsor=sponsor,
        sponsor_class=sponsor_class,
        countries=_countries(study),
        indication=_condition(study),
        provenance=[
            Provenance(
                trial_id=nct,
                snippet=f"{_asset_name(study) or nct} — {_phase(study).value} for {_condition(study)}",
                source_url=f"https://clinicaltrials.gov/study/{nct}",
                field="protocolSection",
            )
        ],
    )
