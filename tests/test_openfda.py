"""openFDA drugsfda client — parses approvals from a recorded-shape response."""

import httpx
import respx

from livemeta.core.sources.openfda import OpenFdaClient

BASE = "https://api.fda.gov/drug/drugsfda.json"

_PAYLOAD = {
    "results": [
        {
            "application_number": "NDA209637",
            "sponsor_name": "NOVO NORDISK INC",
            "openfda": {"brand_name": ["OZEMPIC"], "generic_name": ["SEMAGLUTIDE"]},
            "products": [{"brand_name": "OZEMPIC", "marketing_status": "Prescription"}],
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20171205"},
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20200116"},
            ],
        },
        {
            "application_number": "NDA213051",
            "sponsor_name": "NOVO NORDISK INC",
            "products": [{"brand_name": "RYBELSUS", "marketing_status": "Prescription"}],
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20190920"},
            ],
        },
    ]
}


@respx.mock
def test_parses_approvals_with_earliest_ap_date():
    respx.get(BASE).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    approvals = OpenFdaClient().approvals_for("semaglutide")
    assert [a.application_number for a in approvals] == ["NDA209637", "NDA213051"]
    ozempic = approvals[0]
    assert ozempic.sponsor == "NOVO NORDISK INC"
    assert ozempic.brand_names == ["OZEMPIC"]
    assert ozempic.approval_date == "2017-12-05"  # earliest AP submission
    assert ozempic.marketing_status == "Prescription"
    assert ozempic.indication_approx is None  # openFDA has no indication text
    assert ozempic.provenance[0].trial_id == "NDA209637"


@respx.mock
def test_404_returns_empty_not_error():
    respx.get(BASE).mock(return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND"}}))
    assert OpenFdaClient().approvals_for("nonexistent-drug") == []


@respx.mock
def test_network_error_degrades_to_empty():
    respx.get(BASE).mock(side_effect=httpx.ConnectError("boom"))
    assert OpenFdaClient().approvals_for("semaglutide") == []
