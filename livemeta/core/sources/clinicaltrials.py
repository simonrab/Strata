"""ClinicalTrials.gov v2 API client.

Primary data source: returns structured, arm-level results, which avoids PDF
parsing. https://clinicaltrials.gov/data-api/api
"""

from __future__ import annotations

import httpx

BASE_URL = "https://clinicaltrials.gov/api/v2"


class ClinicalTrialsClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 40.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def fetch_study(self, nct_id: str) -> dict:
        """Full study record (protocol + results) for one trial."""
        resp = httpx.get(f"{self._base}/studies/{nct_id}", timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def search_studies(self, query: str, page_size: int = 20) -> list[dict]:
        """Search by free-text term; return [{nct_id, title}]."""
        resp = httpx.get(
            f"{self._base}/studies",
            params={
                "query.term": query,
                "pageSize": page_size,
                "fields": "protocolSection.identificationModule",
            },
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
