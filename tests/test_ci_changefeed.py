"""The change-feed: deterministic "what moved" between two as-of dates.

Cell-derivable moves (new program, advance, readout, conflict) are unit-tested on
constructed snapshots; evidence moves on constructed version histories; and one
end-to-end pass proves a real stage advance surfaces between two dates.
"""

from livemeta.core.ci import changefeed as cf
from livemeta.core.ci.schema import (
    ChangeType,
    DevelopmentEvent,
    EventType,
    Landscape,
    LandscapeCell,
    Phase,
    SourceType,
)
from livemeta.core.schema import SnapshotMeta
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


def _cell(asset, indication="Obesity", phase=Phase.PHASE_2, event=None, conflict=False, note=None):
    return LandscapeCell(
        asset_name=asset,
        indication=indication,
        current_phase=phase,
        latest_event=event,
        conflict=conflict,
        conflict_note=note,
    )


def _ls(cells):
    return Landscape(condition="Obesity", cells=cells)


# --- diff_landscapes (pure) -------------------------------------------------


def test_new_program_is_a_cell_present_only_at_until():
    prev = _ls([])
    curr = _ls([_cell("Retatrutide", phase=Phase.PHASE_2)])
    changes = cf.diff_landscapes(prev, curr)
    assert [c.change_type for c in changes] == [ChangeType.NEW_PROGRAM]
    assert changes[0].to_phase == Phase.PHASE_2


def test_advance_is_a_higher_stage_for_the_same_cell():
    prev = _ls([_cell("Tirzepatide", phase=Phase.PHASE_2)])
    curr = _ls([_cell("Tirzepatide", phase=Phase.PHASE_3)])
    change = next(c for c in cf.diff_landscapes(prev, curr) if c.change_type == ChangeType.ADVANCED)
    assert change.from_phase == Phase.PHASE_2 and change.to_phase == Phase.PHASE_3
    assert "→" in change.summary


def test_readout_only_when_the_latest_event_is_dated_after_since():
    readout = DevelopmentEvent(
        asset_name="Semaglutide",
        indication="Obesity",
        phase=Phase.PHASE_3,
        event_type=EventType.READOUT,
        date="2026-06-02",
        source_type=SourceType.CTGOV,
    )
    cell = _cell("Semaglutide", phase=Phase.PHASE_3, event=readout)
    curr = _ls([cell])
    # Readout dated inside the window surfaces...
    inside = cf.diff_landscapes(_ls([cell]), curr, since="2026-01-01", until="2026-12-31")
    assert any(c.change_type == ChangeType.READOUT for c in inside)
    # ...but a readout before the window does not (it already happened).
    outside = cf.diff_landscapes(_ls([cell]), curr, since="2026-07-01", until="2026-12-31")
    assert not any(c.change_type == ChangeType.READOUT for c in outside)


def test_conflict_opened_only_when_newly_true():
    prev = _ls([_cell("Survodutide", conflict=False)])
    curr = _ls([_cell("Survodutide", conflict=True, note="ctgov says Ph2, announcement says Ph3")])
    kinds = [c.change_type for c in cf.diff_landscapes(prev, curr)]
    assert ChangeType.CONFLICT_OPENED in kinds
    # Already-conflicting is not re-reported.
    steady = cf.diff_landscapes(curr, curr)
    assert ChangeType.CONFLICT_OPENED not in [c.change_type for c in steady]


# --- _significant + evidence moves ------------------------------------------


def test_significant_is_measure_aware():
    assert cf._significant("HR", 0.74, 0.89) is True  # excludes 1
    assert cf._significant("HR", 0.79, 1.05) is False  # crosses 1
    assert cf._significant("MD", 0.2, 1.5) is True  # excludes 0
    assert cf._significant("HR", None, None) is None


def _snap(version, created_at, estimate, ci_low, ci_high, measure="HR"):
    return SnapshotMeta(
        question_id="q",
        version=version,
        created_at=created_at,
        k=version + 2,
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        measure=measure,
    )


def test_evidence_move_flips_significance_in_window():
    snaps = [
        _snap(1, "2026-01-05", 0.86, 0.79, 1.02),  # baseline: not significant
        _snap(2, "2026-06-09", 0.81, 0.74, 0.89),  # in-window: now significant
    ]
    change = cf._evidence_change("Tirzepatide", "Obesity", snaps, since="2026-03-01", until=None)
    assert change is not None
    assert change.change_type == ChangeType.EVIDENCE_MOVED
    assert change.summary == "Benefit now proven"
    assert change.estimate_prev == 0.86 and change.estimate_curr == 0.81


def test_no_evidence_move_when_no_new_version_in_window():
    snaps = [_snap(1, "2026-01-05", 0.81, 0.74, 0.89)]
    assert cf._evidence_change("X", "Obesity", snaps, since="2026-03-01", until=None) is None


# --- end-to-end -------------------------------------------------------------


def test_landscape_changes_surfaces_a_setback_with_its_reason(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Obesity",), phases=("PHASE3",), status="TERMINATED",
               start="2020-01", primary_completion="2021-06", why_stopped="Lack of efficacy",
               interventions=(("DRUG", "DrugX"),)),
    ]
    diff = cf.landscape_changes(
        store, "Obesity", since="2020-06-01", until="2022-01-01",
        search_pipeline=lambda c: studies,
    )
    setback = next(c for c in diff.changes if c.change_type == ChangeType.SETBACK)
    assert setback.asset_name == "DrugX"
    assert "Lack of efficacy" in setback.summary
    # A halt is never reported as a readout.
    assert not any(c.change_type == ChangeType.READOUT for c in diff.changes)


def test_landscape_changes_surfaces_a_real_advance_between_two_dates(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Obesity",), phases=("PHASE2",), status="RECRUITING",
               start="2019-01", primary_completion=None, interventions=(("DRUG", "DrugA"),)),
        _study(nct="NCT2", conditions=("Obesity",), phases=("PHASE3",), status="RECRUITING",
               start="2021-06", primary_completion=None, interventions=(("DRUG", "DrugA"),)),
    ]
    diff = cf.landscape_changes(
        store, "Obesity", since="2020-06-01", until="2022-01-01",
        search_pipeline=lambda c: studies,
    )
    advance = next(c for c in diff.changes if c.change_type == ChangeType.ADVANCED)
    assert advance.asset_name == "DrugA"
    assert advance.from_phase == Phase.PHASE_2 and advance.to_phase == Phase.PHASE_3
