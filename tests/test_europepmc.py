"""Europe PMC client — search + full-text/abstract fetch (mocked here).

The second data source: for trials whose effect data is not in a structured
ClinicalTrials.gov field, we read the published record from Europe PMC. The
client returns a normalized, deliberately *unstructured* document (title,
abstract, full text, parsed tables); Claude does the structured reading
downstream (see test_extract_text.py).
"""

import httpx
import respx

from livemeta.core.sources.europepmc import EuropePmcClient

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@respx.mock
def test_search_returns_pmids():
    payload = {
        "resultList": {
            "result": [
                {"id": "12345678", "source": "MED", "pmid": "12345678", "title": "Trial A"},
                {"id": "PMC7654321", "source": "PMC", "pmcid": "PMC7654321", "title": "Trial B"},
            ]
        }
    }
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json=payload))
    hits = EuropePmcClient().search_studies("GLP-1 cardiovascular", page_size=2)
    assert [h["id"] for h in hits] == ["PMID:12345678", "PMC7654321"]
    assert hits[0]["title"] == "Trial A"


@respx.mock
def test_fetch_parses_abstract_and_fulltext_xml():
    # Metadata (abstract) comes from /search; open-access full text from fullTextXML.
    meta = {
        "resultList": {
            "result": [
                {
                    "id": "12345678",
                    "source": "MED",
                    "pmid": "12345678",
                    "pmcid": "PMC7654321",
                    "title": "A cardiovascular outcomes trial",
                    "abstractText": "The primary endpoint occurred in 40/500 vs 60/500.",
                    "isOpenAccess": "Y",
                }
            ]
        }
    }
    full_text_xml = """<article>
      <body>
        <sec><p>Full text body paragraph.</p></sec>
        <table-wrap id="t1">
          <label>Table 1</label>
          <caption><p>Primary outcome by arm</p></caption>
          <table>
            <thead><tr><th>Arm</th><th>Events</th><th>Total</th></tr></thead>
            <tbody>
              <tr><td>Treatment</td><td>40</td><td>500</td></tr>
              <tr><td>Control</td><td>60</td><td>500</td></tr>
            </tbody>
          </table>
        </table-wrap>
      </body>
    </article>"""
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json=meta))
    respx.get(f"{BASE}/PMC7654321/fullTextXML").mock(
        return_value=httpx.Response(200, text=full_text_xml)
    )

    doc = EuropePmcClient().fetch_study("PMID:12345678")
    assert doc["id"] == "PMID:12345678"
    assert doc["source"] == "europepmc"
    assert "40/500" in doc["abstract"]
    assert "Full text body paragraph." in doc["full_text"]
    # Tables are parsed as tables, not flattened.
    assert doc["tables"]
    table = doc["tables"][0]
    assert "Primary outcome" in table["caption"]
    assert ["Treatment", "40", "500"] in table["rows"]


@respx.mock
def test_fetch_without_open_access_falls_back_to_abstract():
    meta = {
        "resultList": {
            "result": [
                {
                    "id": "999",
                    "source": "MED",
                    "pmid": "999",
                    "title": "Closed-access trial",
                    "abstractText": "Mean change was 10 (SD 2) vs 8 (SD 2.5).",
                    "isOpenAccess": "N",
                }
            ]
        }
    }
    respx.get(f"{BASE}/search").mock(return_value=httpx.Response(200, json=meta))
    doc = EuropePmcClient().fetch_study("PMID:999")
    assert doc["abstract"].startswith("Mean change")
    assert doc["full_text"] == ""
    assert doc["tables"] == []
