"""Deterministic CT.gov -> TrialDetail (the enriched per-trial record for v2).

Countries, enrolment, readout status, dates — all direct structured reads with
provenance. No Claude here.
"""

import httpx
import respx

from livemeta.core.ci import ctgov_pipeline as cp
from livemeta.core.ci.schema import Phase
from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

BASE = "https://clinicaltrials.gov/api/v2"


def _study_detail(
    nct="NCT05000001",
    title="A Trial of Semaglutide in Obesity",
    phases=("PHASE3",),
    status="COMPLETED",
    start="2018-10",
    primary_completion="2023-06",
    results_posted="2024-08-30",
    has_results=True,
    enrollment=17604,
    sponsor="Novo Nordisk A/S",
    sponsor_class="INDUSTRY",
    conditions=("Obesity", "Overweight"),
    interventions=(("DRUG", "Semaglutide"), ("DRUG", "Placebo")),
    countries=("United States", "United Kingdom", "United States"),
):
    status_mod = {
        "overallStatus": status,
        "startDateStruct": {"date": start},
    }
    if primary_completion:
        status_mod["primaryCompletionDateStruct"] = {"date": primary_completion}
    if results_posted:
        status_mod["resultsFirstPostDateStruct"] = {"date": results_posted}
    return {
        "hasResults": has_results,
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": title},
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor, "class": sponsor_class}
            },
            "designModule": {
                "phases": list(phases),
                "enrollmentInfo": {"count": enrollment},
            },
            "statusModule": status_mod,
            "conditionsModule": {"conditions": list(conditions)},
            "armsInterventionsModule": {
                "interventions": [{"type": t, "name": n} for t, n in interventions]
            },
            "contactsLocationsModule": {
                "locations": [{"country": c} for c in countries]
            },
            "eligibilityModule": {
                "minimumAge": "45 Years",
                "sex": "ALL",
                "eligibilityCriteria": "Adults with BMI >= 30 and established cardiovascular disease.",
            },
        },
    }


def test_trial_detail_reads_core_structured_fields():
    d = cp.study_to_trial_detail(_study_detail())
    assert d.nct_id == "NCT05000001"
    assert d.asset_name == "Semaglutide"
    assert d.phase == Phase.PHASE_3
    assert d.enrollment == 17604
    assert d.sponsor == "Novo Nordisk A/S"
    assert d.indication == "Obesity"
    assert d.start_date == "2018-10-01"
    assert d.primary_completion_date == "2023-06-01"


def test_countries_are_deduped_across_locations():
    d = cp.study_to_trial_detail(_study_detail())
    assert sorted(d.countries) == ["United Kingdom", "United States"]


def test_readout_flag_and_date():
    d = cp.study_to_trial_detail(_study_detail())
    assert d.has_results is True
    assert d.results_posted_date == "2024-08-30"

    ongoing = cp.study_to_trial_detail(
        _study_detail(status="RECRUITING", has_results=False, results_posted=None, primary_completion=None)
    )
    assert ongoing.has_results is False
    assert ongoing.results_posted_date is None


def test_provenance_points_to_the_trial():
    d = cp.study_to_trial_detail(_study_detail())
    assert d.provenance and d.provenance[0].trial_id == "NCT05000001"


def test_missing_modules_do_not_crash():
    d = cp.study_to_trial_detail(
        {"protocolSection": {"identificationModule": {"nctId": "NCT9"}}}
    )
    assert d.nct_id == "NCT9"
    assert d.countries == []
    assert d.enrollment is None


@respx.mock
def test_search_by_intervention_uses_query_intervention_and_wide_fields():
    payload = {"studies": [_study_detail(nct="NCT1"), _study_detail(nct="NCT2")]}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json=payload)
    )
    studies = ClinicalTrialsClient().search_by_intervention("semaglutide")
    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in studies] == ["NCT1", "NCT2"]
    params = route.calls.last.request.url.params
    assert params.get("query.intr") == "semaglutide"
    fields = params.get("fields")
    for module in ("contactsLocationsModule", "eligibilityModule", "designModule"):
        assert module in fields


@respx.mock
def test_search_by_condition_uses_query_cond():
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json={"studies": []})
    )
    ClinicalTrialsClient().search_by_condition("obesity")
    assert route.calls.last.request.url.params.get("query.cond") == "obesity"
