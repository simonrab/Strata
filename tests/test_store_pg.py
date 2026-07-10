"""Postgres store contract — the same behaviour as the SQLite store, verified
against a real Postgres (Supabase) when TEST_DATABASE_URL is set.

Runs in a throwaway schema so it never disturbs the app's `public` tables, and
skips entirely when no test database is configured, keeping the default suite
network-free. The scenarios mirror tests/test_store.py one-for-one: the two
backends implement one interface, so they must satisfy one contract.
"""

from __future__ import annotations

import os
import uuid

import pytest

from livemeta.core.schema import (
    PICO,
    CIMethod,
    EffectMeasure,
    PoolResult,
    Question,
    ReviewDecision,
    ReviewResult,
    RobDecision,
    SnapshotMeta,
)

_DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not _DSN, reason="TEST_DATABASE_URL not set; skipping live Postgres contract"
)


@pytest.fixture
def store():
    """A Postgres store bound to a unique, disposable schema."""
    from livemeta.core.store_pg import PostgresSnapshotStore

    schema = f"livemeta_test_{uuid.uuid4().hex[:12]}"
    s = PostgresSnapshotStore(dsn=_DSN, schema=schema)
    try:
        yield s
    finally:
        s.drop_schema()


def _review(summary: str, qid: str = "q-demo") -> ReviewResult:
    q = Question(
        id=qid,
        text="demo",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
    )
    return ReviewResult(question=q, summary=summary)


def _review_with_pool(estimate: float, qid: str = "q-demo") -> ReviewResult:
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


def test_save_increments_versions_and_load_latest_returns_newest(store):
    v1 = store.save_snapshot(_review("first"))
    v2 = store.save_snapshot(_review("second"))

    assert v1 == 1
    assert v2 == 2
    assert store.list_versions("q-demo") == [1, 2]
    assert store.load_latest("q-demo").summary == "second"


def test_load_latest_missing_returns_none(store):
    assert store.load_latest("does-not-exist") is None
    assert store.list_versions("does-not-exist") == []


def test_list_questions_returns_saved_question_ids(store):
    assert store.list_questions() == []
    store.save_snapshot(_review("a", qid="glp1-mace"))
    store.save_snapshot(_review("b", qid="sglt2-hf"))
    assert sorted(store.list_questions()) == ["glp1-mace", "sglt2-hf"]


def test_decisions_round_trip_and_default_empty(store):
    assert store.load_decisions("q-demo") == []
    store.save_snapshot(_review("first"))
    store.save_decision(
        "q-demo", ReviewDecision(study_id="NCT01", decision="flagged", reason="bad arm")
    )
    store.save_decision("q-demo", ReviewDecision(study_id="NCT02", decision="confirmed"))

    by_id = {d.study_id: d.decision for d in store.load_decisions("q-demo")}
    assert by_id == {"NCT01": "flagged", "NCT02": "confirmed"}

    store.save_decision("q-demo", ReviewDecision(study_id="NCT01", decision="confirmed"))
    by_id = {d.study_id: d.decision for d in store.load_decisions("q-demo")}
    assert by_id["NCT01"] == "confirmed"
    assert store.list_versions("q-demo") == [1]


def test_rob_decisions_round_trip_latest_per_domain_wins(store):
    assert store.load_rob_decisions("q-demo") == []
    store.save_snapshot(_review("first"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D1"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D2"))
    store.save_rob_decision(
        "q-demo", RobDecision(study_id="NCT01", domain_key="D1", reason="re-checked")
    )

    decisions = store.load_rob_decisions("q-demo")
    keys = {(d.study_id, d.domain_key) for d in decisions}
    assert keys == {("NCT01", "D1"), ("NCT01", "D2")}
    d1 = next(d for d in decisions if d.domain_key == "D1")
    assert d1.reason == "re-checked"
    assert store.load_decisions("q-demo") == []
    assert store.list_versions("q-demo") == [1]


def test_load_version_returns_the_specific_version(store):
    store.save_snapshot(_review("first"))
    store.save_snapshot(_review("second"))
    store.save_snapshot(_review("third"))

    assert store.load_version("q-demo", 2).summary == "second"
    assert store.load_version("q-demo", 1).summary == "first"
    assert store.load_version("q-demo", 99) is None
    assert store.load_version("nope", 1) is None


def test_list_snapshots_returns_meta_with_timestamps(store):
    store.save_snapshot(_review_with_pool(0.88))
    store.save_snapshot(_review_with_pool(0.86))

    metas = store.list_snapshots("q-demo")
    assert [m.version for m in metas] == [1, 2]
    assert all(isinstance(m, SnapshotMeta) for m in metas)
    assert all(m.created_at for m in metas)
    assert metas[0].created_at <= metas[1].created_at
    assert metas[0].k == 8
    assert round(metas[1].estimate, 2) == 0.86
    assert store.list_snapshots("nope") == []


# --- competitive-intelligence: events + evidence links (mirror test_ci_store) --


def _dev_event(asset, indication, phase, date):
    from livemeta.core.ci.schema import (
        DevelopmentEvent,
        EventType,
        Phase,
        SourceType,
    )
    from livemeta.core.schema import Provenance

    return DevelopmentEvent(
        asset_name=asset,
        indication=indication,
        phase=Phase(phase),
        date=date,
        event_type=EventType.TRIAL_START,
        source_type=SourceType.CTGOV,
        provenance=[Provenance(trial_id="NCT_x", snippet="s")],
    )


def test_events_round_trip_and_scoped_by_landscape(store):
    assert store.load_events("t2d") == []
    store.save_events("t2d", [_dev_event("DrugA", "T2D", "phase_2", "2016-01-01")])
    store.save_events("nsclc", [_dev_event("DrugZ", "NSCLC", "phase_1", "2016-01-01")])
    assert [e.asset_name for e in store.load_events("t2d")] == ["DrugA"]
    assert [e.asset_name for e in store.load_events("nsclc")] == ["DrugZ"]


def test_reingesting_same_milestone_is_idempotent(store):
    store.save_events("t2d", [_dev_event("DrugA", "T2D", "phase_2", "2016-01-01")])
    store.save_events("t2d", [_dev_event("DrugA", "T2D", "phase_3", "2016-01-01")])
    loaded = store.load_events("t2d")
    assert len(loaded) == 1
    assert loaded[0].phase.value == "phase_3"


def test_clear_events_drops_a_landscapes_cache(store):
    store.save_events("t2d", [_dev_event("DrugA", "T2D", "phase_2", "2016-01-01")])
    store.save_events("nsclc", [_dev_event("DrugZ", "NSCLC", "phase_1", "2016-01-01")])
    store.clear_events("t2d")
    assert store.load_events("t2d") == []
    assert [e.asset_name for e in store.load_events("nsclc")] == ["DrugZ"]


def test_links_round_trip_and_upsert(store):
    assert store.load_links("t2d") == {}
    store.save_link("t2d", "DrugA", "T2D", "glp1-mace")
    assert store.load_links("t2d") == {("DrugA", "T2D"): "glp1-mace"}
    store.save_link("t2d", "DrugA", "T2D", "glp1-mace-v2")
    assert store.load_links("t2d") == {("DrugA", "T2D"): "glp1-mace-v2"}


def test_subpop_and_approvals_cache_round_trip(store):
    from livemeta.core.ci.schema import RegulatoryApproval, SubPopulation

    assert store.load_subpops(["NCT1"]) == {}
    store.save_subpop("NCT1", SubPopulation(base_indication="Obesity", comorbidities=["ckd"]))
    store.save_subpop("NCT1", SubPopulation(base_indication="Obesity", comorbidities=["t2d"]))
    got = store.load_subpops(["NCT1", "NCT2"])
    assert set(got) == {"NCT1"} and got["NCT1"].comorbidities == ["t2d"]

    assert store.load_approvals("semaglutide") == []
    store.save_approvals([
        RegulatoryApproval(drug="semaglutide", application_number="NDA1"),
    ])
    assert [a.application_number for a in store.load_approvals("semaglutide")] == ["NDA1"]


def test_load_all_links_spans_landscapes(store):
    store.save_link("obesity", "Semaglutide", "Obesity", "sema-mace")
    store.save_link("t2d", "Tirzepatide", "T2D", "tirz-mace")
    assert store.load_all_links()[("Semaglutide", "Obesity")] == "sema-mace"
