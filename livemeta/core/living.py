"""The living layer: add a trial to an existing review, re-run, and diff.

A leaf module shared by the MCP `update` tool and the REST update endpoint so the
two cannot diverge. It imports the pipeline and the diff, never `grade` at module
top, keeping it clear of the grade<->pipeline import cycle.
"""

from __future__ import annotations

from collections.abc import Callable

from . import search as search_mod
from .diff import diff_reviews
from .pipeline import run_review_collect
from .schema import ReviewDiff, TrialCandidate
from .store import SnapshotStore

FetchStudy = Callable[[str], dict]


def apply_update(
    store: SnapshotStore,
    question_id: str,
    new_trial_id: str,
    fetch_study: FetchStudy,
) -> ReviewDiff:
    """Add `new_trial_id` to a saved review, re-pool, persist a new version, diff.

    Returns the new pooled estimate, the added trial, and — the load-bearing
    signal — whether the conclusion changed (a flip in statistical significance
    or in the direction of effect). Raises ValueError if no baseline exists.
    """
    previous = store.load_latest(question_id)
    if previous is None:
        raise ValueError(
            f"No existing review for question_id {question_id!r}; run a review first."
        )
    previous_version = store.list_versions(question_id)[-1]

    trial_ids = list(previous.question.trial_ids)
    if new_trial_id not in trial_ids:
        trial_ids.append(new_trial_id)
    new_question = previous.question.model_copy(update={"trial_ids": trial_ids})

    current = run_review_collect(new_question, fetch_study)
    current_version = store.save_snapshot(current)

    return diff_reviews(
        previous,
        current,
        previous_version=previous_version,
        current_version=current_version,
    )


def check_for_new_trials(
    store: SnapshotStore, question_id: str, search_client=None
) -> list[TrialCandidate]:
    """Re-search a saved question's PICO and return only genuinely-new trials.

    This is what makes "updates itself as new results land" real: on demand, the
    tool re-runs the same PICO search it used to build the review, then diffs the
    returned NCT ids against the ids already in the latest snapshot. Candidates
    already in the review are dropped, so what comes back is exactly the set a
    reviewer could inject via `apply_update`. It never auto-pools — discovery and
    the decision to update stay separate. Raises ValueError if no baseline exists.
    """
    previous = store.load_latest(question_id)
    if previous is None:
        raise ValueError(
            f"No existing review for question_id {question_id!r}; run a review first."
        )

    seen = set(previous.question.trial_ids)
    candidates = search_mod.search_trials(previous.question.pico, client=search_client)
    return [c for c in candidates if c.nct_id and c.nct_id not in seen]
