"""PubMed / openFDA are opt-in, off by default.

ClinicalTrials.gov is always on. PubMed (Europe PMC) and openFDA only activate
when a caller names them — via the `sources=` param (API/MCP) or the CLI flags —
and their live clients are provisioned only then. These tests pin that contract
at each seam so the sources can't silently turn on by default again.
"""

from livemeta.api import app as api_app
from livemeta.core.ci.schema import Source, explicitly_selected
from livemeta.core.sources.europepmc import EuropePmcClient
from livemeta.core.sources.openfda import OpenFdaClient
from livemeta.mcp import server as mcp_server


# --- the shared helper -------------------------------------------------------


def test_explicitly_selected_requires_an_explicit_name():
    assert explicitly_selected("ctgov,openfda", Source.OPENFDA) is True
    assert explicitly_selected("ctgov,pubmed", Source.PUBMED) is True
    # Absent / None / unrelated -> off. A blank param never opts anything in, even
    # though the default SourceSelection *allows* the whole structured trio.
    assert explicitly_selected(None, Source.OPENFDA) is False
    assert explicitly_selected("", Source.PUBMED) is False
    assert explicitly_selected("ctgov", Source.OPENFDA) is False
    assert explicitly_selected("ctgov", Source.PUBMED) is False


def test_explicitly_selected_tolerates_whitespace_and_case():
    assert explicitly_selected(" CTGOV , OpenFDA ", Source.OPENFDA) is True


# --- API providers -----------------------------------------------------------


def test_api_get_openfda_off_by_default_on_when_named():
    assert api_app.get_openfda(None) is None
    assert api_app.get_openfda("ctgov,pubmed") is None
    client = api_app.get_openfda("ctgov,openfda")
    assert isinstance(client, OpenFdaClient)


def test_api_get_discovery_adds_pubmed_only_when_named(monkeypatch):
    captured = {}

    def fake_search_trials(pico, *, client=None, epmc_client=None, **kw):
        captured["epmc"] = epmc_client
        return []

    monkeypatch.setattr(api_app.search_mod, "search_trials", fake_search_trials)

    api_app.get_discovery(None)("pico")
    assert captured["epmc"] is None

    api_app.get_discovery("ctgov,pubmed")("pico")
    assert isinstance(captured["epmc"], EuropePmcClient)


# --- MCP provider ------------------------------------------------------------


def test_mcp_openfda_for_off_by_default_on_when_named():
    # No test-injected client and no explicit request -> None.
    mcp_server.set_openfda(None)
    assert mcp_server._openfda_for(None) is None
    assert mcp_server._openfda_for("ctgov,pubmed") is None
    assert isinstance(mcp_server._openfda_for("ctgov,openfda"), OpenFdaClient)


def test_mcp_openfda_for_prefers_injected_client():
    sentinel = object()
    mcp_server.set_openfda(sentinel)
    try:
        # An injected client (tests) wins regardless of the sources param.
        assert mcp_server._openfda_for(None) is sentinel
        assert mcp_server._openfda_for("ctgov,openfda") is sentinel
    finally:
        mcp_server.set_openfda(None)
