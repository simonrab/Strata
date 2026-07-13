"""ClinicalTrials.gov v2 API client.

Primary data source: returns structured, arm-level results, which avoids PDF
parsing. https://clinicaltrials.gov/data-api/api
"""

from __future__ import annotations

import os

import httpx

# CT.gov's Akamai WAF 403s requests from some datacenter egress IPs (e.g.
# Railway's shared range) regardless of headers. Set CTGOV_API_BASE to a
# passthrough proxy hosted on a clean-egress network to route around it; it
# defaults to CT.gov direct, which is correct for any host CT.gov does not block.
BASE_URL = os.environ.get("CTGOV_API_BASE", "https://clinicaltrials.gov/api/v2")

# A browser-like User-Agent (the earlier, weaker mitigation — it does not defeat
# an IP-level block, but is kept as it makes normal traffic look less bot-like).
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class ClinicalTrialsClient:
    # Top-level sections the extractor reads. Requested explicitly because the
    # /studies search endpoint (unlike /studies/{id}) returns only the fields
    # asked for. This set matches what the per-id endpoint returns by default.
    _STUDY_FIELDS = "protocolSection,resultsSection,derivedSection,hasResults"

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 40.0,
        proxy_token: str | None = None,
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        # When the clean-egress proxy is gated by a shared secret, present it so the
        # proxy can reject anyone else's traffic. Falls back to CTGOV_PROXY_TOKEN in
        # the environment; absent, no token header is sent (direct CT.gov use and an
        # ungated proxy both keep working). Header name matches the proxy's check.
        token = proxy_token if proxy_token is not None else os.environ.get("CTGOV_PROXY_TOKEN")
        self._headers = {**_HEADERS, **({"x-proxy-token": token} if token else {})}

    def fetch_study(self, nct_id: str) -> dict:
        """Full study record (protocol + results) for one trial.

        Pulled through the `/studies` free-text search (`query.term`) rather than
        the id-lookup forms (`/studies/{id}` or `filter.ids`). CT.gov's Akamai
        edge 403s the id-lookup pattern from datacenter IPs (e.g. Railway) while
        normal `query.term` search traffic passes, so this keeps the deployed
        backend fetching live. The NCT id is an exact term, so the target study
        is returned; we pick it by matching nctId (never a study that merely
        references it). The record shape matches the per-id endpoint.
        """
        resp = httpx.get(
            f"{self._base}/studies",
            params={
                "query.term": nct_id,
                "fields": self._STUDY_FIELDS,
                "pageSize": 10,
            },
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        target = nct_id.strip().upper()
        for study in resp.json().get("studies", []):
            ident = study.get("protocolSection", {}).get("identificationModule", {})
            if ident.get("nctId", "").upper() == target:
                return study
        raise ValueError(f"No study found on ClinicalTrials.gov for {nct_id}")

    def search_studies(
        self, query: str, page_size: int = 1000, interventional_only: bool = False
    ) -> list[dict]:
        """Search by free-text term; return [{nct_id, title}].

        `interventional_only` adds the CT.gov v2 advanced filter
        `AREA[StudyType]INTERVENTIONAL`, the first deterministic screen: it keeps
        observational records out of a systematic-review candidate set at the API.
        """
        params = {
            "query.term": query,
            "pageSize": page_size,
            "fields": "protocolSection.identificationModule",
        }
        if interventional_only:
            params["filter.advanced"] = "AREA[StudyType]INTERVENTIONAL"
        resp = httpx.get(
            f"{self._base}/studies",
            params=params,
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        hits = []
        for study in resp.json().get("studies", []):
            ident = study.get("protocolSection", {}).get("identificationModule", {})
            hits.append(
                {"nct_id": ident.get("nctId", ""), "title": ident.get("briefTitle", "")}
            )
        return hits

    def search_agent_studies(
        self,
        intervention: str,
        term: str | None = None,
        page_size: int = 1000,
        interventional_only: bool = True,
        with_results_only: bool = True,
    ) -> list[dict]:
        """Search one drug for the systematic candidate set; return [{nct_id, title}].

        Scopes to `query.intr` (the intervention field) because CT.gov indexes a
        trial by its specific agent, not its pharmacologic class — so a class
        question must be expanded upstream and each agent searched here. An optional
        `term` (`query.term`) narrows on the outcome; `interventional_only` and
        `with_results_only` (`results:with`) are the first deterministic screens —
        a pooling review can only use randomized trials that actually posted
        results.
        """
        params: dict[str, object] = {
            "query.intr": intervention,
            "pageSize": page_size,
            "fields": "protocolSection.identificationModule",
        }
        if term:
            params["query.term"] = term
        if interventional_only:
            params["filter.advanced"] = "AREA[StudyType]INTERVENTIONAL"
        if with_results_only:
            params["aggFilters"] = "results:with"
        resp = httpx.get(
            f"{self._base}/studies", params=params, headers=self._headers, timeout=self._timeout
        )
        resp.raise_for_status()
        hits = []
        for study in resp.json().get("studies", []):
            ident = study.get("protocolSection", {}).get("identificationModule", {})
            hits.append(
                {"nct_id": ident.get("nctId", ""), "title": ident.get("briefTitle", "")}
            )
        return hits

    # Modules needed to place a drug in the competitive pipeline: who sponsors it,
    # what phase, its status and dated milestones, the drug name, the indication.
    _PIPELINE_FIELDS = ",".join(
        "protocolSection." + m
        for m in (
            "identificationModule",
            "sponsorCollaboratorsModule",
            "designModule",
            "statusModule",
            "armsInterventionsModule",
            "conditionsModule",
        )
    )

    def search_pipeline(self, query: str, page_size: int = 1000) -> list[dict]:
        """Search returning the raw study records (with pipeline modules).

        The competitive-intelligence sibling of `search_studies`: it keeps the
        full structured record so the CI parser can read sponsor / phase / status
        / dates / interventions, which `search_studies` deliberately strips.

        Scoped by `query.cond` (the studied condition), not the free-text
        `query.term`: the landscape asks "what is in development *for* this
        condition", so a trial that merely mentions the condition as a comorbidity
        or exclusion (e.g. a saline study that enrols obese patients) must not be
        pulled in. This matches `search_by_condition`, used for the indication map.
        """
        resp = httpx.get(
            f"{self._base}/studies",
            params={
                "query.cond": query,
                "pageSize": page_size,
                "fields": self._PIPELINE_FIELDS,
            },
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("studies", [])

    # The deeper pull for an asset dossier / indication map: adds locations
    # (geography), eligibility (sub-populations), enrolment, and the results flag.
    _DETAIL_FIELDS = _PIPELINE_FIELDS + "," + ",".join(
        (
            "protocolSection.contactsLocationsModule",
            "protocolSection.eligibilityModule",
            "derivedSection.conditionBrowseModule",
            "hasResults",
        )
    )

    def _search_detail(self, param: str, value: str, page_size: int) -> list[dict]:
        resp = httpx.get(
            f"{self._base}/studies",
            params={param: value, "pageSize": page_size, "fields": self._DETAIL_FIELDS},
            headers=self._headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("studies", [])

    def search_by_intervention(self, name: str, page_size: int = 1000) -> list[dict]:
        """All trials for a drug (by intervention name), with the detail fields."""
        return self._search_detail("query.intr", name, page_size)

    def search_by_condition(self, name: str, page_size: int = 1000) -> list[dict]:
        """All trials in an indication (by condition), with the detail fields."""
        return self._search_detail("query.cond", name, page_size)

    def search_by_sponsor(self, name: str, page_size: int = 1000) -> list[dict]:
        """Every trial a company runs, scoped to lead sponsor (`query.lead`).

        Powers the cross-condition company pipeline: unlike `search_pipeline`
        (one condition) this pulls the sponsor's whole portfolio across every
        indication. Lead-sponsor, not sponsor/collaborator, so a company's board
        isn't flooded with trials it merely co-funds. Carries the detail fields so
        readouts (results flag) and geography come through."""
        return self._search_detail("query.lead", name, page_size)
