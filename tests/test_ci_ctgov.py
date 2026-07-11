"""Deterministic CT.gov → competitive-intelligence parsing.

No Claude here: sponsor/phase/status/dates/interventions come straight from the
structured CT.gov v2 record the tool already fetches. Every derived event carries
provenance back to the trial. Mirrors the "no silent back-calculation" contract.
"""

import httpx
import respx

from livemeta.core.ci import ctgov_pipeline as cp
from livemeta.core.ci.schema import EventType, Phase, SourceType
from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

BASE = "https://clinicaltrials.gov/api/v2"


def _study(
    nct="NCT01234567",
    title="A Trial of Semaglutide in Type 2 Diabetes",
    phases=("PHASE3",),
    status="COMPLETED",
    start="2015-03",
    primary_completion="2018-06",
    sponsor="Novo Nordisk",
    sponsor_class="INDUSTRY",
    conditions=("Type 2 Diabetes",),
    interventions=(("DRUG", "Semaglutide"), ("DRUG", "Placebo")),
    why_stopped=None,
):
    status_module = {
        "overallStatus": status,
        "startDateStruct": {"date": start},
        "primaryCompletionDateStruct": {"date": primary_completion},
    }
    if why_stopped is not None:
        status_module["whyStopped"] = why_stopped
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": title},
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor, "class": sponsor_class}
            },
            "designModule": {"phases": list(phases)},
            "statusModule": status_module,
            "conditionsModule": {"conditions": list(conditions)},
            "armsInterventionsModule": {
                "interventions": [{"type": t, "name": n} for t, n in interventions]
            },
        }
    }


# --- study_to_asset ---------------------------------------------------------


def test_asset_reads_drug_sponsor_and_class():
    asset = cp.study_to_asset(_study())
    assert asset.name == "Semaglutide"  # the non-placebo drug arm
    assert asset.sponsor == "Novo Nordisk"
    assert asset.sponsor_class == "INDUSTRY"
    assert asset.provenance and asset.provenance[0].trial_id == "NCT01234567"


def test_asset_skips_placebo_and_control_arms():
    study = _study(interventions=(("DRUG", "Placebo"), ("DRUG", "Tirzepatide")))
    assert cp.study_to_asset(study).name == "Tirzepatide"


# --- study_to_events --------------------------------------------------------


def test_events_emit_start_and_readout_with_phase_and_provenance():
    events = cp.study_to_events(_study())
    kinds = {e.event_type for e in events}
    assert EventType.TRIAL_START in kinds
    assert EventType.READOUT in kinds  # COMPLETED with a primary-completion date
    for e in events:
        assert e.phase == Phase.PHASE_3
        assert e.indication == "Type 2 Diabetes"
        assert e.source_type == SourceType.CTGOV
        assert e.provenance and e.provenance[0].trial_id == "NCT01234567"


def test_start_event_dated_and_normalized_to_iso():
    start = next(
        e for e in cp.study_to_events(_study()) if e.event_type == EventType.TRIAL_START
    )
    assert start.date == "2015-03-01"  # "YYYY-MM" padded to a sortable ISO date


def test_readout_only_when_completed_with_a_date():
    ongoing = _study(status="RECRUITING", primary_completion=None)
    kinds = {e.event_type for e in cp.study_to_events(ongoing)}
    assert EventType.READOUT not in kinds
    assert EventType.TRIAL_START in kinds


def test_terminated_is_a_setback_with_the_reason_not_a_readout():
    study = _study(status="TERMINATED", why_stopped="Lack of efficacy")
    events = cp.study_to_events(study)
    kinds = {e.event_type for e in events}
    # A halt must NOT masquerade as a readout.
    assert EventType.READOUT not in kinds
    assert EventType.SETBACK in kinds
    setback = next(e for e in events if e.event_type == EventType.SETBACK)
    # The CT.gov reason is carried through, so "lack of efficacy" is visible.
    assert "Lack of efficacy" in setback.provenance[0].snippet
    assert setback.status == "TERMINATED"


def test_withdrawn_and_suspended_are_setbacks():
    for status in ("WITHDRAWN", "SUSPENDED"):
        kinds = {e.event_type for e in cp.study_to_events(_study(status=status))}
        assert EventType.SETBACK in kinds


def test_completed_still_reads_out_not_a_setback():
    kinds = {e.event_type for e in cp.study_to_events(_study(status="COMPLETED"))}
    assert EventType.READOUT in kinds
    assert EventType.SETBACK not in kinds


def test_indication_picks_the_condition_matching_the_landscape_focus():
    # Obesity is a comorbidity here, listed after the primary condition. The
    # landscape focus should pull "Obesity" as the indication, not "Hypertension".
    study = _study(conditions=("Hypertension", "Obesity"))
    focused = cp.study_to_events(study, focus_condition="Obesity")
    assert all(e.indication == "Obesity" for e in focused)
    # Without a focus, behaviour is unchanged: the first listed condition.
    assert all(e.indication == "Hypertension" for e in cp.study_to_events(study))


def test_indication_uses_the_searched_area_when_trial_names_no_subtype():
    # Obesity is incidental here (a breast-cancer trial CT.gov linked to obesity).
    # Label the cell with the searched area, not the off-target comorbidity, so
    # "Breast Cancer" never leaks into an obesity landscape's indication list.
    study = _study(conditions=("Breast Cancer",))
    focused = cp.study_to_events(study, focus_condition="Obesity")
    assert all(e.indication == "Obesity" for e in focused)


def test_phase_mapping_combined_phase_2_3():
    events = cp.study_to_events(_study(phases=("PHASE2", "PHASE3")))
    assert all(e.phase == Phase.PHASE_2_3 for e in events)


def test_missing_modules_do_not_crash():
    events = cp.study_to_events({"protocolSection": {"identificationModule": {"nctId": "NCT9"}}})
    # No dated milestones, but never raises; any event carries the trial id.
    for e in events:
        assert e.provenance[0].trial_id == "NCT9"


# --- search_pipeline (client) ----------------------------------------------


@respx.mock
def test_search_pipeline_requests_wide_fields_and_returns_raw_studies():
    payload = {"studies": [_study(nct="NCT1"), _study(nct="NCT2")]}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json=payload)
    )
    studies = ClinicalTrialsClient().search_pipeline("obesity", page_size=2)

    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in studies] == [
        "NCT1",
        "NCT2",
    ]
    params = route.calls.last.request.url.params
    # Condition-scoped, not free-text: the landscape must not pull trials that
    # merely mention the condition (a saline study enrolling obese patients).
    assert params.get("query.cond") == "obesity"
    assert params.get("query.term") is None
    fields = params.get("fields")
    for module in (
        "sponsorCollaboratorsModule",
        "designModule",
        "statusModule",
        "armsInterventionsModule",
        "conditionsModule",
    ):
        assert module in fields
    ua = route.calls.last.request.headers.get("user-agent", "")
    assert "Mozilla" in ua  # reuses the browser UA; live backend 403s without it


@respx.mock
def test_search_by_sponsor_scopes_to_lead_sponsor_with_detail_fields():
    payload = {"studies": [_study(nct="NCT1", sponsor="Novo Nordisk")]}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json=payload)
    )
    studies = ClinicalTrialsClient().search_by_sponsor("Novo Nordisk", page_size=1)

    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in studies] == ["NCT1"]
    params = route.calls.last.request.url.params
    # Lead-sponsor scoped: the company pipeline wants trials this company runs,
    # not every trial that merely names it as a collaborator.
    assert params.get("query.lead") == "Novo Nordisk"
    assert params.get("query.cond") is None
    # Detail fields (geography, results flag) so readouts show on the company view.
    assert "contactsLocationsModule" in params.get("fields")
    assert "hasResults" in params.get("fields")
