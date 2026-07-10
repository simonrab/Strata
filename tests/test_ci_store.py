"""CI persistence contract (SQLite): dated events + evidence links.

The Postgres store mirrors these one-for-one in tests/test_store_pg.py; both back
the same interface reached via make_store().
"""

from livemeta.core.ci.schema import DevelopmentEvent, EventType, Phase, SourceType
from livemeta.core.schema import Provenance
from livemeta.core.store import SnapshotStore


def _ev(asset, indication, phase, date, source=SourceType.CTGOV, etype=EventType.TRIAL_START):
    return DevelopmentEvent(
        asset_name=asset,
        indication=indication,
        phase=phase,
        date=date,
        event_type=etype,
        source_type=source,
        provenance=[Provenance(trial_id="NCT_x", snippet="s")],
    )


def test_events_round_trip(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    assert store.load_events("t2d") == []
    store.save_events(
        "t2d",
        [
            _ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01"),
            _ev("DrugB", "T2D", Phase.PHASE_3, "2017-01-01"),
        ],
    )
    loaded = store.load_events("t2d")
    assert {e.asset_name for e in loaded} == {"DrugA", "DrugB"}
    assert loaded[0].provenance[0].trial_id == "NCT_x"


def test_events_are_scoped_by_landscape(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    store.save_events("t2d", [_ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01")])
    store.save_events("nsclc", [_ev("DrugZ", "NSCLC", Phase.PHASE_1, "2016-01-01")])
    assert [e.asset_name for e in store.load_events("t2d")] == ["DrugA"]
    assert [e.asset_name for e in store.load_events("nsclc")] == ["DrugZ"]


def test_reingesting_same_milestone_is_idempotent(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    store.save_events("t2d", [_ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01")])
    # Same natural key (asset/indication/source/type/date), refreshed phase.
    store.save_events("t2d", [_ev("DrugA", "T2D", Phase.PHASE_3, "2016-01-01")])
    loaded = store.load_events("t2d")
    assert len(loaded) == 1
    assert loaded[0].phase == Phase.PHASE_3


def test_clear_events_drops_a_landscapes_cache(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    store.save_events("t2d", [_ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01")])
    store.save_events("nsclc", [_ev("DrugZ", "NSCLC", Phase.PHASE_1, "2016-01-01")])
    store.clear_events("t2d")
    # Only the targeted landscape is emptied; siblings are untouched.
    assert store.load_events("t2d") == []
    assert [e.asset_name for e in store.load_events("nsclc")] == ["DrugZ"]


def test_links_round_trip_and_upsert(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    assert store.load_links("t2d") == {}
    store.save_link("t2d", "DrugA", "T2D", "glp1-mace")
    assert store.load_links("t2d") == {("DrugA", "T2D"): "glp1-mace"}
    store.save_link("t2d", "DrugA", "T2D", "glp1-mace-v2")
    assert store.load_links("t2d") == {("DrugA", "T2D"): "glp1-mace-v2"}
