"""Snapshot store: versioned ReviewResult persistence keyed by question id.

Minimal JSON store standing in for Slice 5's SQLite; the version list is the
audit-trail history.
"""

from livemeta.core.schema import (
    PICO,
    CIMethod,
    EffectMeasure,
    EligibilityDecision,
    PoolResult,
    Question,
    ReviewDecision,
    ReviewResult,
    RobDecision,
    SnapshotMeta,
)
from livemeta.core.store import SnapshotStore


def _review(summary: str, qid: str = "q-demo") -> ReviewResult:
    q = Question(
        id=qid,
        text="demo",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
    )
    return ReviewResult(question=q, summary=summary)


def _review_with_pool(estimate: float, qid: str = "q-demo") -> ReviewResult:
    """A review carrying a pool, so the store's denormalized headline columns
    (k / estimate / ci) have something real to reflect."""
    q = Question(
        id=qid,
        text="demo",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
    )
    pool = PoolResult(
        measure=EffectMeasure.HR,
        engine="python",
        k=8,
        estimate=estimate,
        ci_low=estimate - 0.07,
        ci_high=estimate + 0.08,
        ci_method=CIMethod.HKSJ,
        estimate_log=-0.15,
        se_log=0.04,
        ci_low_log=-0.24,
        ci_high_log=-0.06,
        tau2=0.004,
        i2=45.0,
        q=12.0,
        q_p=0.08,
    )
    return ReviewResult(question=q, pool=pool)


def test_save_increments_versions_and_load_latest_returns_newest(tmp_path):
    store = SnapshotStore(tmp_path)

    v1 = store.save_snapshot(_review("first"))
    v2 = store.save_snapshot(_review("second"))

    assert v1 == 1
    assert v2 == 2
    assert store.list_versions("q-demo") == [1, 2]

    latest = store.load_latest("q-demo")
    assert latest is not None
    assert latest.summary == "second"


def test_load_latest_missing_returns_none(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_latest("does-not-exist") is None
    assert store.list_versions("does-not-exist") == []


def test_list_questions_returns_saved_question_ids(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.list_questions() == []

    store.save_snapshot(_review("a", qid="glp1-mace"))
    store.save_snapshot(_review("b", qid="sglt2-hf"))

    assert sorted(store.list_questions()) == ["glp1-mace", "sglt2-hf"]


def test_decisions_round_trip_and_default_empty(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_decisions("q-demo") == []

    store.save_snapshot(_review("first"))
    store.save_decision(
        "q-demo", ReviewDecision(study_id="NCT01", decision="flagged", reason="bad arm")
    )
    store.save_decision("q-demo", ReviewDecision(study_id="NCT02", decision="confirmed"))

    decisions = store.load_decisions("q-demo")
    assert {d.study_id: d.decision for d in decisions} == {
        "NCT01": "flagged",
        "NCT02": "confirmed",
    }
    # A later decision on the same trial supersedes the earlier one.
    store.save_decision("q-demo", ReviewDecision(study_id="NCT01", decision="confirmed"))
    decisions = store.load_decisions("q-demo")
    by_id = {d.study_id: d.decision for d in decisions}
    assert by_id["NCT01"] == "confirmed"

    # Decisions live alongside snapshots without clobbering the version history.
    assert store.list_versions("q-demo") == [1]


def test_screening_decisions_round_trip_latest_per_trial_wins(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_screening_decisions("q-demo") == []

    store.save_snapshot(_review("first"))
    store.save_screening_decision(
        "q-demo", EligibilityDecision(study_id="NCT01", decision="excluded", by_claude=False)
    )
    store.save_screening_decision(
        "q-demo", EligibilityDecision(study_id="NCT02", decision="included", by_claude=False)
    )
    # A later call on the same trial supersedes the earlier one.
    store.save_screening_decision(
        "q-demo",
        EligibilityDecision(study_id="NCT01", decision="included", by_claude=False, confirmed=True),
    )

    decisions = {d.study_id: d for d in store.load_screening_decisions("q-demo")}
    assert decisions["NCT01"].decision == "included"
    assert decisions["NCT01"].confirmed is True
    assert decisions["NCT02"].decision == "included"
    # Screening sign-offs don't disturb other decision tables or the history.
    assert store.load_decisions("q-demo") == []
    assert store.list_versions("q-demo") == [1]


def test_rob_decisions_round_trip_latest_per_domain_wins(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_rob_decisions("q-demo") == []

    store.save_snapshot(_review("first"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D1"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D2"))
    store.save_rob_decision(
        "q-demo", RobDecision(study_id="NCT01", domain_key="D1", reason="re-checked")
    )

    decisions = store.load_rob_decisions("q-demo")
    # Two distinct (study, domain) sign-offs; the D1 re-check superseded the first.
    keys = {(d.study_id, d.domain_key) for d in decisions}
    assert keys == {("NCT01", "D1"), ("NCT01", "D2")}
    d1 = next(d for d in decisions if d.domain_key == "D1")
    assert d1.reason == "re-checked"
    # RoB sign-offs don't disturb the trial decision list or the version history.
    assert store.load_decisions("q-demo") == []
    assert store.list_versions("q-demo") == [1]


# --- Slice 5: audit-trail read paths -----------------------------------------


def test_load_version_returns_the_specific_version(tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_snapshot(_review("first"))
    store.save_snapshot(_review("second"))
    store.save_snapshot(_review("third"))

    assert store.load_version("q-demo", 2).summary == "second"
    assert store.load_version("q-demo", 1).summary == "first"
    # A version that was never written — or a question that doesn't exist — is None.
    assert store.load_version("q-demo", 99) is None
    assert store.load_version("nope", 1) is None


def test_list_snapshots_returns_meta_with_timestamps(tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_snapshot(_review_with_pool(0.88))
    store.save_snapshot(_review_with_pool(0.86))

    metas = store.list_snapshots("q-demo")
    assert [m.version for m in metas] == [1, 2]
    assert all(isinstance(m, SnapshotMeta) for m in metas)
    # Every snapshot is timestamped, and time only moves forward.
    assert all(m.created_at for m in metas)
    assert metas[0].created_at <= metas[1].created_at
    # Headline pool numbers are denormalized onto the meta (no JSON parse needed).
    assert metas[0].k == 8
    assert round(metas[1].estimate, 2) == 0.86
    # An unknown question has no history.
    assert store.list_snapshots("nope") == []


def test_snapshots_persist_to_a_single_sqlite_db_file(tmp_path):
    store = SnapshotStore(tmp_path)
    store.save_snapshot(_review("first"))

    assert (tmp_path / "livemeta.db").exists()
    # The JSON-per-question layout is gone — nothing but the DB is written.
    assert list(tmp_path.glob("*.json")) == []
