"""SourceRouter — dispatch a reference id to the right evidence source.

NCT ids go to ClinicalTrials.gov; PMID/PMC ids go to Europe PMC. The router is
the pipeline's default fetch, so a review can draw trials from both sources.
Tests inject stub clients — no network.
"""

import pytest

from livemeta.core.sources.router import SourceRouter


class _StubCtgov:
    def fetch_study(self, ref_id):
        return {"source_client": "ctgov", "id": ref_id}

    def search_studies(self, query, page_size=1000):
        return [{"nct_id": "NCT1", "title": "ct"}]


class _StubEpmc:
    def fetch_study(self, ref_id):
        return {"source_client": "epmc", "id": ref_id}

    def search_studies(self, query, page_size=25):
        return [{"id": "PMID:1", "title": "epmc"}]


def _router():
    return SourceRouter(ctgov=_StubCtgov(), europepmc=_StubEpmc())


def test_routes_nct_to_clinicaltrials():
    assert _router().fetch("NCT01179048")["source_client"] == "ctgov"


def test_routes_pmid_to_europepmc():
    assert _router().fetch("PMID:12345678")["source_client"] == "epmc"


def test_routes_pmc_to_europepmc():
    assert _router().fetch("PMC7654321")["source_client"] == "epmc"


def test_unknown_id_shape_raises():
    with pytest.raises(ValueError):
        _router().fetch("whatever-123")
