"""ClinicalTrials.gov v2 client — thin, typed HTTP wrapper (mocked here)."""

import httpx
import respx

from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

BASE = "https://clinicaltrials.gov/api/v2"


@respx.mock
def test_fetch_study_returns_json():
    payload = {"protocolSection": {"identificationModule": {"nctId": "NCT01179048"}}}
    respx.get(f"{BASE}/studies/NCT01179048").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = ClinicalTrialsClient()
    assert client.fetch_study("NCT01179048") == payload


@respx.mock
def test_search_studies_extracts_ids_and_titles():
    payload = {
        "studies": [
            {"protocolSection": {"identificationModule": {"nctId": "NCT1", "briefTitle": "A"}}},
            {"protocolSection": {"identificationModule": {"nctId": "NCT2", "briefTitle": "B"}}},
        ]
    }
    respx.get(f"{BASE}/studies").mock(return_value=httpx.Response(200, json=payload))
    client = ClinicalTrialsClient()
    hits = client.search_studies("GLP-1 cardiovascular", page_size=2)
    assert [h["nct_id"] for h in hits] == ["NCT1", "NCT2"]
    assert hits[0]["title"] == "A"
