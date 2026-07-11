"""Side-by-side compare: operational facts line up; efficacy abstains.

The load-bearing assertions are the safety ones — the comparability gate defaults
to "not directly comparable", and each asset's evidence stays in its own context.
"""

import math

from livemeta.core.ci import compare
from livemeta.core.ci.schema import AssetEvidenceContext, EvidenceBadge
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


def _study_full(nct, asset, indication="Obesity", phase="PHASE3", enrollment=None,
                countries=(), pcd=None, has_results=False, status="RECRUITING"):
    s = _study(nct=nct, conditions=(indication,), phases=(phase,), status=status,
               primary_completion=pcd, interventions=((("DRUG", asset)),))
    if enrollment is not None:
        s["protocolSection"]["designModule"]["enrollmentInfo"] = {"count": enrollment}
    if countries:
        s["protocolSection"]["contactsLocationsModule"] = {
            "locations": [{"country": c} for c in countries]
        }
    if has_results:
        s["protocolSection"]["statusModule"]["resultsFirstPostDateStruct"] = {"date": "2025-01"}
    return s


def _save_linked_review(store, qid, condition, asset, indication):
    from livemeta.core.ci import service

    q = Question(
        id=qid, text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )
    pool = PoolResult(
        measure=EffectMeasure.HR, engine="python", k=4,
        estimate=0.81, ci_low=0.74, ci_high=0.89, ci_method=CIMethod.WALD,
        estimate_log=math.log(0.81), se_log=0.04, ci_low_log=-0.30, ci_high_log=-0.12,
        tau2=0.0, i2=10.0, q=1.0, q_p=0.9,
    )
    store.save_snapshot(ReviewResult(question=q, pool=pool))
    service.link_review(store, condition, asset, indication, qid)


def _ctx(measure="HR", state="pooled", population="obesity", comparator=None):
    badge = EvidenceBadge(question_id="q", measure=measure, state=state,
                          estimate=0.8, ci_low=0.7, ci_high=0.9)
    return AssetEvidenceContext(asset_name="x", population=population,
                               comparator=comparator, badge=badge)


# --- the comparability gate (the safety core) -------------------------------


def test_unanchored_comparison_is_not_directly_comparable():
    # Same measure, same population, both pooled — but no common comparator.
    verdict = compare.assess_comparability(_ctx(), _ctx())
    assert verdict.directly_comparable is False
    assert any("comparator" in r for r in verdict.reasons)


def test_different_measures_are_flagged_incomparable():
    verdict = compare.assess_comparability(_ctx(measure="HR"), _ctx(measure="MD"))
    assert verdict.directly_comparable is False
    assert any("outcome measures" in r for r in verdict.reasons)


def test_anchored_identical_context_is_comparable():
    a = _ctx(comparator="placebo")
    b = _ctx(comparator="placebo")
    assert compare.assess_comparability(a, b).directly_comparable is True


# --- end-to-end -------------------------------------------------------------


def test_compare_lines_up_operational_facts_and_abstains_on_efficacy(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    catalog = {
        "DrugA": [_study_full("NCT1", "DrugA", enrollment=12500,
                              countries=("US", "UK", "DE"), pcd="2026-11")],
        "DrugB": [_study_full("NCT2", "DrugB", enrollment=17600,
                              countries=("US", "UK", "DE", "FR", "JP"), pcd=None)],
    }
    _save_linked_review(store, "a-mace", "Obesity", "DrugA", "Obesity")

    result = compare.compare_assets(
        store, ["DrugA", "DrugB"], indication="Obesity",
        search=lambda asset: catalog.get(asset, []), as_of="2026-01-01",
    )

    rows = {r.label: r for r in result.rows}
    assert rows["Trials"].values == ["1", "1"]
    assert rows["Running"].values == ["1", "1"]  # both RECRUITING
    assert rows["Completed"].values == ["0", "0"]
    assert rows["Countries"].values == ["3", "5"]
    assert rows["Countries"].more == [False, True]  # neutral marker on the larger
    assert rows["Next readout"].values == ["2026-11-01", "—"]

    # The misleading "most advanced phase" / "biggest study" rows are gone; efficacy
    # is never a comparison row.
    assert "Lead phase" not in rows and "Enrollment" not in rows
    assert "Estimate" not in rows

    # Each asset's evidence stands in its own context (not rendered, but present).
    assert [e.asset_name for e in result.evidence] == ["DrugA", "DrugB"]
    assert result.comparability.directly_comparable is False


def test_compare_counts_statuses_and_shows_the_phase_spread(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    catalog = {
        "DrugX": [
            _study_full("N1", "DrugX", phase="PHASE3", status="RECRUITING"),
            _study_full("N2", "DrugX", phase="PHASE3", status="COMPLETED", has_results=True),
            _study_full("N3", "DrugX", phase="PHASE4", status="ACTIVE_NOT_RECRUITING"),
            # An observational registry — no phase → falls under NA, not "Phase 4".
            _study_full("N4", "DrugX", phase="NA", status="RECRUITING"),
            # A halted trial — counted as Terminated, not Running/Completed.
            _study_full("N5", "DrugX", phase="PHASE3", status="TERMINATED"),
        ],
    }
    result = compare.compare_assets(
        store, ["DrugX", "DrugX"], indication="Obesity",
        search=lambda a: catalog["DrugX"], as_of="2026-01-01",
    )
    rows = {r.label: r for r in result.rows}
    assert rows["Trials"].values[0] == "5"
    assert rows["Running"].values[0] == "3"  # RECRUITING×2 + ACTIVE_NOT_RECRUITING
    assert rows["Completed"].values[0] == "1"
    assert rows["Terminated"].values[0] == "1"
    # The distribution is visible — Ph3, Ph4, and NA all show, not a single "Phase 4".
    assert rows["Phases"].values[0] == "Ph3 3 · Ph4 1 · NA 1"
