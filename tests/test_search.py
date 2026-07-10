"""Trial search: PICO -> query -> candidates, mapped from CT.gov v2.

The HTTP layer is mocked with respx so the test runs offline.
"""

import httpx
import respx

from livemeta.core import search
from livemeta.core.schema import PICO, TrialCandidate

STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"


def _pico() -> PICO:
    return PICO(
        population="adults with type 2 diabetes",
        intervention="GLP-1 receptor agonist",
        comparator="placebo",
        outcome="MACE",
    )


def test_build_query_includes_intervention_and_outcome():
    q = search.build_query(_pico())
    assert "GLP-1" in q
    assert "MACE" in q


def test_build_query_excludes_comparator_and_population():
    # Comparator ("placebo") and population over-constrain CT.gov's AND-match, so
    # they are left out of the search term (still used downstream).
    q = search.build_query(_pico()).lower()
    assert "placebo" not in q
    assert "diabetes" not in q  # population term absent
    assert "glp-1 receptor agonist" in q
    assert "mace" in q


@respx.mock
def test_search_trials_maps_hits_to_candidates():
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {
                                "nctId": "NCT01179048",
                                "briefTitle": "LEADER",
                            }
                        }
                    }
                ]
            },
        )
    )

    hits = search.search_trials(_pico(), max_results=5)

    assert route.called
    assert hits == [TrialCandidate(nct_id="NCT01179048", title="LEADER")]


@respx.mock
def test_search_trials_default_cap_is_1000():
    # The default candidate cap is CT.gov's per-request max, so broad questions
    # aren't silently truncated.
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    search.search_trials(_pico())

    assert route.called
    assert route.calls.last.request.url.params["pageSize"] == "1000"


@respx.mock
def test_search_trials_filters_to_interventional_by_default():
    # First deterministic screen: narrow the candidate set to interventional
    # trials at the API so observational records never enter the pipeline.
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    search.search_trials(_pico())

    assert route.called
    adv = route.calls.last.request.url.params["filter.advanced"]
    assert "StudyType" in adv and "INTERVENTIONAL" in adv


@respx.mock
def test_search_studies_omits_filter_when_not_interventional_only():
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

    ClinicalTrialsClient().search_studies("GLP-1 MACE")  # default: no design filter

    assert "filter.advanced" not in route.calls.last.request.url.params
