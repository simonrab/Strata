"""The shared living-update core: add a trial, re-run, diff.

Used by both the MCP `update` tool and the REST update endpoint, so they cannot
diverge. Driven offline from recorded fixtures.
"""

import json
from pathlib import Path

import pytest

from livemeta.core import living
from livemeta.core.demo import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
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
