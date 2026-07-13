"""ClinicalTrials.gov v2 client — thin, typed HTTP wrapper (mocked here)."""

import httpx
import respx

from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

BASE = "https://clinicaltrials.gov/api/v2"


@respx.mock
def test_fetch_study_selects_exact_id_from_query_term_search():
    # The record is pulled via the /studies free-text search (query.term), not
    # /studies/{id} or filter.ids: CT.gov's Akamai edge 403s the id-lookup
    # pattern from datacenter IPs (e.g. Railway) while query.term search passes.
    # A term search can also surface studies that merely reference the id, so
    # fetch_study returns the one whose nctId matches exactly.
    target = {"protocolSection": {"identificationModule": {"nctId": "NCT01179048"}}}
    other = {"protocolSection": {"identificationModule": {"nctId": "NCT99999999"}}}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json={"studies": [other, target]})
    )
    client = ClinicalTrialsClient()
    assert client.fetch_study("NCT01179048") == target
    assert route.calls.last.request.url.params.get("query.term") == "NCT01179048"
    assert "filter.ids" not in route.calls.last.request.url.params


@respx.mock
def test_fetch_study_raises_when_id_not_found():
    # No returned study matches the requested id.
    respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(
            200,
            json={"studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT88888888"}}}
            ]},
        )
    )
    client = ClinicalTrialsClient()
    try:
        client.fetch_study("NCT_MISSING")
    except ValueError as e:
        assert "NCT_MISSING" in str(e)
    else:
        raise AssertionError("expected ValueError for an unknown NCT id")


@respx.mock
def test_fetch_study_sends_browser_user_agent():
    # CT.gov returns 403 to the default python-httpx UA from datacenter IPs
    # (e.g. Railway); a real User-Agent header is required in production.
    study = {"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json={"studies": [study]})
    )
    ClinicalTrialsClient().fetch_study("NCT1")
    ua = route.calls.last.request.headers.get("user-agent", "")
    assert "python-httpx" not in ua
    assert "Mozilla" in ua


@respx.mock
def test_fetch_study_honours_custom_base_url_for_proxying():
    # A clean-egress proxy is wired by pointing the client at it (CTGOV_API_BASE
    # sets this base in production). Requests must go to the proxy host, not CT.gov.
    proxy = "https://ctgov-proxy.example.com/api/v2"
    study = {"protocolSection": {"identificationModule": {"nctId": "NCT01179048"}}}
    route = respx.get(f"{proxy}/studies").mock(
        return_value=httpx.Response(200, json={"studies": [study]})
    )
    client = ClinicalTrialsClient(base_url=proxy)
    assert client.fetch_study("NCT01179048") == study
    assert route.calls.last.request.url.host == "ctgov-proxy.example.com"


@respx.mock
def test_fetch_study_sends_proxy_token_when_configured():
    # The clean-egress proxy is a public, unauthenticated endpoint unless a shared
    # secret gates it. When CTGOV_PROXY_TOKEN is set, the client must present it as
    # the x-proxy-token header so the proxy can reject anyone else's traffic.
    study = {"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json={"studies": [study]})
    )
    ClinicalTrialsClient(proxy_token="s3cret").fetch_study("NCT1")
    assert route.calls.last.request.headers.get("x-proxy-token") == "s3cret"


@respx.mock
def test_fetch_study_omits_proxy_token_header_by_default():
    # With no shared secret configured, no token header is sent (direct CT.gov use
    # and an unauthenticated proxy both keep working).
    study = {"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json={"studies": [study]})
    )
    ClinicalTrialsClient(proxy_token=None).fetch_study("NCT1")
    assert "x-proxy-token" not in route.calls.last.request.headers


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
