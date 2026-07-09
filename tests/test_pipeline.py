"""Unit tests for re-pooling after human confirm/flag decisions.

The human-in-the-loop gate is load-bearing: a reviewer's *flag* must remove a
trial from the pool and change the estimate; a *confirm* records sign-off without
altering poolability. These assertions guard that contract.
"""

import json
from pathlib import Path

from livemeta.core import demo
from livemeta.core.pipeline import repool_with_decisions, run_review_collect
from livemeta.core.schema import ReviewDecision

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct: str) -> dict:
    return json.loads((FIXTURES / f"{nct}.json").read_text())


def _baseline():
    return run_review_collect(demo.GLP1_MACE_QUESTION, _fetch)


def test_baseline_pools_all_eight():
    review = _baseline()
    assert review.pool is not None
    assert review.pool.k == 8
    assert round(review.pool.estimate, 2) == 0.86


def test_flagging_a_trial_removes_it_from_the_pool():
    baseline = _baseline()
    target = baseline.extractions[0].study_id

    repooled = repool_with_decisions(
        baseline,
        [ReviewDecision(study_id=target, decision="flagged", reason="reviewer flagged")],
    )

    assert repooled.pool is not None
    assert repooled.pool.k == 7
    pooled_ids = {s.study_id for s in repooled.pool.studies}
    assert target not in pooled_ids

    flagged = next(e for e in repooled.extractions if e.study_id == target)
    assert flagged.flagged is True
    assert flagged.flag_reason == "reviewer flagged"


def test_confirming_a_trial_keeps_it_and_records_signoff():
    baseline = _baseline()
    target = baseline.extractions[0].study_id

    repooled = repool_with_decisions(
        baseline, [ReviewDecision(study_id=target, decision="confirmed")]
    )

    assert repooled.pool is not None
    assert repooled.pool.k == 8
    confirmed = next(e for e in repooled.extractions if e.study_id == target)
    assert confirmed.confirmed is True
    assert confirmed.flagged is False


def test_summary_is_recomputed_after_repool():
    baseline = _baseline()
    ids = [e.study_id for e in baseline.extractions]

    # Flag all but two trials — the estimate and k in the summary must update.
    decisions = [ReviewDecision(study_id=i, decision="flagged") for i in ids[:6]]
    repooled = repool_with_decisions(baseline, decisions)

    assert repooled.pool is not None
    assert repooled.pool.k == 2
    assert "2 trials" in repooled.summary


def test_run_fetches_every_trial_with_no_cap(monkeypatch):
    # No run cap: a review fetches all candidates (concurrently). 40 trials means
    # 40 fetches, all pooled. (Fast Python engine so 40 studies pool quickly.)
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    sample = _fetch("NCT01179048")
    fetched: list[str] = []

    def counting_fetch(nct: str) -> dict:
        fetched.append(nct)
        return sample

    question = demo.GLP1_MACE_QUESTION.model_copy(
        update={"trial_ids": [f"NCT{i:08d}" for i in range(40)]}
    )
    result = run_review_collect(question, counting_fetch)

    assert len(fetched) == 40
    assert result.pool is not None
    assert result.pool.k == 40


def test_rob_is_scoped_to_pooled_trials_only(monkeypatch):
    # RoB must appraise only the trials that make the pool, not every candidate:
    # non-poolable trials (no extractable HR) are excluded from the RoB list.
    monkeypatch.setenv("LIVEMETA_STATS_ENGINE", "python")
    good = ["NCT01179048", "NCT01720446", "NCT02465515"]  # real fixtures with HRs
    bad = ["NCTBAD0001", "NCTBAD0002"]  # no results section -> flagged, not pooled

    def fetch(nct: str) -> dict:
        if nct in bad:
            return {"protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}}}
        return _fetch(nct)

    question = demo.GLP1_MACE_QUESTION.model_copy(update={"trial_ids": good + bad})
    result = run_review_collect(question, fetch)

    assert result.pool is not None
    assert result.pool.k == 3
    # RoB covers exactly the 3 pooled trials — the 2 unpoolable ones are excluded.
    assert len(result.rob) == 3
    assert {r.study_id for r in result.rob} == set(good)
