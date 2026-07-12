"""The shared living-update core: add a trial, re-run, diff.

Used by both the MCP `update` tool and the REST update endpoint, so they cannot
diverge. Driven offline from recorded fixtures.
"""

import json
from pathlib import Path

import pytest

from livemeta.core import living
from tests.glp1_fixtures import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import ReviewDiff
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


def test_apply_update_adds_trial_and_diffs(tmp_path):
    store = SnapshotStore(tmp_path)
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    store.save_snapshot(run_review_collect(q7, _fetch))  # v1: 7-trial baseline

    diff = living.apply_update(store, "glp1-mace", GLP1_CVOT_TRIALS[7], _fetch)

    assert isinstance(diff, ReviewDiff)
    assert diff.k_curr == 8
    assert GLP1_CVOT_TRIALS[7] in diff.added_trials
    # The re-run is persisted as a new version — the audit trail.
    assert store.list_versions("glp1-mace") == [1, 2]


def test_apply_update_missing_review_raises(tmp_path):
    store = SnapshotStore(tmp_path)
    with pytest.raises(ValueError):
        living.apply_update(store, "does-not-exist", GLP1_CVOT_TRIALS[0], _fetch)


# --- On-demand "check for new trials": make the living claim real ------------


class _FakeSearchClient:
    """Stands in for the CT.gov client: returns a fixed hit list for the re-search."""

    def __init__(self, nct_ids):
        self._ids = list(nct_ids)

    def search_studies(self, query, page_size=1000, interventional_only=False):
        return [{"nct_id": nct, "title": nct} for nct in self._ids]

    def search_agent_studies(self, intervention, term=None, page_size=1000, **kwargs):
        return [{"nct_id": nct, "title": nct} for nct in self._ids]


def _seed_baseline(store) -> None:
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    store.save_snapshot(run_review_collect(q7, _fetch))  # v1: 7-trial baseline


def test_check_for_new_trials_returns_only_unseen(tmp_path):
    store = SnapshotStore(tmp_path)
    _seed_baseline(store)

    # The re-search surfaces the 7 already-pooled trials, the held-out 8th, and an
    # unrelated new record; only genuinely-new ids come back.
    search = _FakeSearchClient(GLP1_CVOT_TRIALS + ["NCT99999999"])
    new = living.check_for_new_trials(store, "glp1-mace", search)

    ids = [c.nct_id for c in new]
    assert GLP1_CVOT_TRIALS[7] in ids  # AMPLITUDE-O, the real held-out readout
    assert "NCT99999999" in ids
    assert all(seen not in ids for seen in GLP1_CVOT_TRIALS[:7])


def test_check_for_new_trials_empty_when_nothing_new(tmp_path):
    store = SnapshotStore(tmp_path)
    _seed_baseline(store)

    search = _FakeSearchClient(GLP1_CVOT_TRIALS[:7])  # only already-seen trials
    new = living.check_for_new_trials(store, "glp1-mace", search)

    assert new == []


def test_check_then_inject_flows_through_apply_update(tmp_path):
    store = SnapshotStore(tmp_path)
    _seed_baseline(store)

    search = _FakeSearchClient(GLP1_CVOT_TRIALS)
    [candidate] = living.check_for_new_trials(store, "glp1-mace", search)

    diff = living.apply_update(store, "glp1-mace", candidate.nct_id, _fetch)
    assert isinstance(diff, ReviewDiff)
    assert diff.k_curr == 8
    assert store.list_versions("glp1-mace") == [1, 2]


def test_check_for_new_trials_missing_review_raises(tmp_path):
    store = SnapshotStore(tmp_path)
    with pytest.raises(ValueError):
        living.check_for_new_trials(store, "does-not-exist", _FakeSearchClient([]))
