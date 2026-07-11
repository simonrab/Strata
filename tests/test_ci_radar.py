"""The milestone radar: forward-looking expected readouts, bucketed by quarter.

Deterministic — a fixed `as_of` makes "future" reproducible with no clock.
"""

from livemeta.core.ci import radar
from livemeta.core.ci.schema import MilestoneKind
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


def _with_results(study):
    study["protocolSection"]["statusModule"]["resultsFirstPostDateStruct"] = {"date": "2025-12"}
    return study


def test_quarter_bucketing_is_calendar_quarters():
    assert radar._quarter("2026-08-01") == "2026-Q3"
    assert radar._quarter("2026-11-01") == "2026-Q4"
    assert radar._quarter("2027-02-01") == "2027-Q1"


def test_horizon_cutoff_adds_months():
    assert radar._horizon_cutoff("2026-01-01", 12) == "2027-01-01"
    assert radar._horizon_cutoff("2026-08-01", 6) == "2027-02-01"


def test_radar_keeps_future_unreported_readouts_within_horizon(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        # In-window future readout — kept.
        _study(nct="NCT1", conditions=("Obesity",), phases=("PHASE3",), status="RECRUITING",
               primary_completion="2026-08", interventions=(("DRUG", "Retatrutide"),)),
        # Already read out (has results) — dropped.
        _with_results(
            _study(nct="NCT2", conditions=("Obesity",), phases=("PHASE3",), status="COMPLETED",
                   primary_completion="2026-09", interventions=(("DRUG", "Semaglutide"),))
        ),
        # Completion in the past relative to as_of — dropped.
        _study(nct="NCT3", conditions=("Obesity",), phases=("PHASE2",), status="RECRUITING",
               primary_completion="2025-06", interventions=(("DRUG", "OldDrug"),)),
        # Beyond the 12-month horizon — dropped.
        _study(nct="NCT4", conditions=("Obesity",), phases=("PHASE2",), status="RECRUITING",
               primary_completion="2028-01", interventions=(("DRUG", "FarDrug"),)),
        # Terminated with a future completion date — a halted trial won't read out.
        _study(nct="NCT5", conditions=("Obesity",), phases=("PHASE3",), status="TERMINATED",
               primary_completion="2026-08", interventions=(("DRUG", "DeadDrug"),)),
    ]
    result = radar.milestone_radar(
        store, "Obesity", search=lambda c: studies, horizon_months=12, as_of="2026-01-01"
    )
    assets = [m.asset_name for m in result.milestones]
    assert assets == ["Retatrutide"]
    m = result.milestones[0]
    assert m.quarter == "2026-Q3"
    assert m.kind == MilestoneKind.EXPECTED_READOUT
    assert m.expected_date == "2026-08-01"


def test_radar_sorts_by_expected_date(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Obesity",), phases=("PHASE3",), status="RECRUITING",
               primary_completion="2026-11", interventions=(("DRUG", "Later"),)),
        _study(nct="NCT2", conditions=("Obesity",), phases=("PHASE2",), status="RECRUITING",
               primary_completion="2026-08", interventions=(("DRUG", "Sooner"),)),
    ]
    result = radar.milestone_radar(
        store, "Obesity", search=lambda c: studies, horizon_months=18, as_of="2026-01-01"
    )
    assert [m.asset_name for m in result.milestones] == ["Sooner", "Later"]


def test_radar_degrades_when_search_unavailable(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)

    def boom(scope):
        raise RuntimeError("403 from CT.gov")

    result = radar.milestone_radar(store, "Obesity", search=boom, as_of="2026-01-01")
    assert result.milestones == []
    assert any("unavailable" in n for n in result.notes)
