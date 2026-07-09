"""openFDA drugsfda client — regulatory approvals for an asset.

Structured, authoritative: drug, sponsor, application number, brand(s), approval
date, marketing status. openFDA does NOT return the approved *indication* text
(that lives in the label PDF), so `indication_approx` is left None — approvals are
reported without over-claiming what they were approved *for*.
"""

from __future__ import annotations

import httpx

from ..ci.schema import RegulatoryApproval
from ..schema import Provenance

BASE_URL = "https://api.fda.gov/drug/drugsfda.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _fmt_date(raw: str | None) -> str | None:
    """openFDA dates are YYYYMMDD -> ISO YYYY-MM-DD."""
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def _approval_date(result: dict) -> str | None:
    """Earliest 'AP' (approved) submission date across a result's submissions."""
    dates = [
        _fmt_date(s.get("submission_status_date"))
        for s in result.get("submissions", [])
        if s.get("submission_status") == "AP"
    ]
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _brand_names(result: dict) -> list[str]:
    names: list[str] = []
    for p in result.get("products", []):
        name = (p.get("brand_name") or "").strip()
        if name and name not in names:
            names.append(name)
    for name in result.get("openfda", {}).get("brand_name", []):
        if name and name not in names:
            names.append(name)
    return names


def _marketing_status(result: dict) -> str | None:
    products = result.get("products", [])
    return products[0].get("marketing_status") if products else None


class OpenFdaClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0):
        self._base = base_url
        self._timeout = timeout

    def approvals_for(self, drug: str, limit: int = 20) -> list[RegulatoryApproval]:
        """Regulatory approvals whose generic name matches `drug` (empty on miss)."""
        try:
            resp = httpx.get(
                self._base,
                params={"search": f'openfda.generic_name:"{drug}"', "limit": limit},
                headers=_HEADERS,
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            return []
        if resp.status_code == 404:  # openFDA returns 404 when nothing matches
            return []
        resp.raise_for_status()

        approvals: list[RegulatoryApproval] = []
        for result in resp.json().get("results", []):
            app_no = result.get("application_number", "")
            if not app_no:
                continue
            approvals.append(
                RegulatoryApproval(
                    drug=drug,
                    sponsor=result.get("sponsor_name"),
                    application_number=app_no,
                    brand_names=_brand_names(result),
                    approval_date=_approval_date(result),
                    marketing_status=_marketing_status(result),
                    indication_approx=None,
                    provenance=[
                        Provenance(
                            trial_id=app_no,
                            snippet=(
                                f"{drug} — {app_no} "
                                f"({', '.join(_brand_names(result)) or 'no brand'})"
                            ),
                            source_url="https://api.fda.gov/drug/drugsfda.json",
                            field="openfda.drugsfda",
                        )
                    ],
                )
            )
        return approvals
