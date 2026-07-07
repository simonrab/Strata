"""The MCP tool surface, driven offline.

Each tool is a thin wrapper over the same core the FastAPI pipeline uses, so the
`pool` tool must reproduce the Slice-1 answer (parity check). The CT.gov client
and the snapshot store are injected via the server's DI seams.
"""

import json
from pathlib import Path

import pytest

from livemeta.core.demo import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import ReviewDiff, ReviewResult, TrialCandidate, TrialExtraction
from livemeta.core.store import SnapshotStore
from livemeta.mcp import server

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureClient:
    """Stands in for ClinicalTrialsClient: fixtures for fetch, canned search."""

    def fetch_study(self, nct_id: str) -> dict:
        return json.loads((FIXTURES / f"{nct_id}.json").read_text())

    def search_studies(self, query: str, page_size: int = 20) -> list[dict]:
        return [{"nct_id": "NCT01179048", "title": "LEADER"}]


@pytest.fixture(autouse=True)
def wired(tmp_path):
    server.set_client(FixtureClient())
    server.set_store(SnapshotStore(tmp_path))
    yield


def test_search_trials_returns_candidates():
    p = GLP1_MACE_QUESTION.pico
    hits = server.search_trials(p.population, p.intervention, p.comparator, p.outcome)
    assert hits and isinstance(hits[0], TrialCandidate)
    assert hits[0].nct_id == "NCT01179048"


def test_extract_effects_returns_extraction_with_provenance():
    ext = server.extract_effects("NCT01179048")
    assert isinstance(ext, TrialExtraction)
    assert ext.study_id == "NCT01179048"
    assert not ext.flagged
    assert ext.provenance[0].snippet


def test_validate_and_pool_reproduce_slice1_answer():
    extractions = [server.extract_effects(nct) for nct in GLP1_CVOT_TRIALS]
    dumped = [e.model_dump() for e in extractions]

    validations = server.validate(dumped)
    assert all(v.passed for v in validations)

    pool = server.pool(dumped, measure="HR")
    assert pool.k == 8
    assert round(pool.estimate, 2) == 0.86
    assert pool.ci_method == "hksj"


def test_run_review_saves_snapshot_and_returns_result():
    result = server.run_review("glp1-mace")
    assert isinstance(result, ReviewResult)
    assert result.pool is not None
    assert round(result.pool.estimate, 2) == 0.86
    # snapshot persisted so `update` has a baseline
    assert server.get_store().list_versions("glp1-mace") == [1]


def test_parse_question_recognizes_the_locked_demo():
    q = server.parse_question(GLP1_MACE_QUESTION.text)
    assert q.id == "glp1-mace"
    assert len(q.trial_ids) == 8


def test_record_decision_flags_trial_and_repools():
    server.run_review("glp1-mace")
    target = GLP1_CVOT_TRIALS[0]

    result = server.record_decision("glp1-mace", target, "flagged", "unclear arm")

    assert result.pool.k == 7
    assert target not in {s.study_id for s in result.pool.studies}
    assert server.get_store().list_versions("glp1-mace") == [1, 2]


def test_update_adds_trial_and_reports_diff():
    # Seed a 7-trial baseline via core, then let `update` add the 8th.
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    seeded = run_review_collect(q7, FixtureClient().fetch_study)
    server.get_store().save_snapshot(seeded)

    diff = server.update("glp1-mace", GLP1_CVOT_TRIALS[7])

    assert isinstance(diff, ReviewDiff)
    assert diff.k_curr == 8
    assert GLP1_CVOT_TRIALS[7] in diff.added_trials
    assert isinstance(diff.conclusion_changed, bool)
    # the re-run is persisted as a new version
    assert server.get_store().list_versions("glp1-mace") == [1, 2]
