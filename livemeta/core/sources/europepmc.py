"""Europe PMC REST client — the second data source.

For trials whose effect data is not in a structured ClinicalTrials.gov field, we
read the published record from Europe PMC: metadata + abstract from `/search`,
and open-access full text (JATS XML, tables parsed as tables) from
`/{source}/{id}/fullTextXML`. https://europepmc.org/RestfulWebService

This client only *retrieves and normalizes* text — it never reads effect data.
Claude does the structured reading downstream (`extract.extract_from_text`), so
the "model reads, code computes" split is preserved.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _canonical_id(result: dict) -> str:
    """A stable reference id: prefer PMC (open access), else PMID:<n>."""
    if result.get("pmcid"):
        return result["pmcid"]
    pmid = result.get("pmid") or result.get("id")
    return f"PMID:{pmid}"


class EuropePmcClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 40.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def search_studies(self, query: str, page_size: int = 25) -> list[dict]:
        """Search Europe PMC; return [{id, pmid, pmcid, title}]."""
        resp = httpx.get(
            f"{self._base}/search",
            params={
                "query": query,
                "format": "json",
                "pageSize": page_size,
                "resultType": "lite",
            },
            headers=_HEADERS,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        hits = []
        for r in resp.json().get("resultList", {}).get("result", []):
            hits.append(
                {
                    "id": _canonical_id(r),
                    "pmid": r.get("pmid"),
                    "pmcid": r.get("pmcid"),
                    "title": r.get("title", ""),
                }
            )
        return hits

    def fetch_study(self, ref_id: str) -> dict:
        """A normalized document for one reference: title, abstract, full text, tables.

        Metadata + abstract always come from `/search`; open-access full text is
        pulled from `fullTextXML` and its tables parsed as tables. Non-OA records
        degrade to the abstract alone — honest about what can be read.
        """
        result = self._lookup(ref_id)
        abstract = result.get("abstractText", "") if result else ""
        title = result.get("title", "") if result else ""

        full_text, tables = "", []
        # Open-access full-text XML is served by PMCID at /{PMCID}/fullTextXML.
        if (
            result
            and str(result.get("isOpenAccess", "")).upper() == "Y"
            and result.get("pmcid")
        ):
            full_text, tables = self._fetch_full_text(result["pmcid"])

        return {
            "id": ref_id,
            "source": "europepmc",
            "title": title,
            "abstract": abstract,
            "full_text": full_text,
            "tables": tables,
        }

    # --- internals ----------------------------------------------------------

    def _lookup(self, ref_id: str) -> dict | None:
        """Resolve a ref id to its Europe PMC record (for abstract + source/id)."""
        raw = ref_id.split(":", 1)[1] if ref_id.upper().startswith("PMID:") else ref_id
        query = f"PMCID:{raw}" if raw.upper().startswith("PMC") else f"EXT_ID:{raw}"
        resp = httpx.get(
            f"{self._base}/search",
            params={"query": query, "format": "json", "resultType": "core"},
            headers=_HEADERS,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        results = resp.json().get("resultList", {}).get("result", [])
        return results[0] if results else None

    def _fetch_full_text(self, pmcid: str) -> tuple[str, list[dict]]:
        resp = httpx.get(
            f"{self._base}/{pmcid}/fullTextXML",
            headers={"User-Agent": _HEADERS["User-Agent"]},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            return "", []
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return "", []
        return _body_text(root), _parse_tables(root)


def _body_text(root: ET.Element) -> str:
    """Flattened prose of the article body (paragraphs), tables excluded."""
    paras = []
    for p in root.iter("p"):
        text = "".join(p.itertext()).strip()
        if text:
            paras.append(text)
    return "\n".join(paras)


def _parse_tables(root: ET.Element) -> list[dict]:
    """Each JATS <table-wrap> as {caption, rows: [[cell, ...], ...]} — tables as tables."""
    tables: list[dict] = []
    for tw in root.iter("table-wrap"):
        caption = " ".join(
            "".join(c.itertext()).strip()
            for c in list(tw.iter("caption")) + list(tw.iter("label"))
        ).strip()
        rows: list[list[str]] = []
        for tr in tw.iter("tr"):
            cells = [
                "".join(cell.itertext()).strip()
                for cell in tr
                if cell.tag in ("td", "th")
            ]
            if cells:
                rows.append(cells)
        tables.append({"caption": caption, "rows": rows})
    return tables
