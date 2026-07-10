"""Landscape service: seeding, ingest, linking, and the evidence join together.

Uses a real SQLite store, a fake CT.gov search (canned studies), and a stub LLM
client — no network, no key.
"""

from livemeta.core.ci import service
from livemeta.core.ci.schema import Phase
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study  # reuse the CT.gov fixture builder
from tests.test_ci_ingest import _StubClient, _ext


def _search(studies):
    return lambda condition: studies


def test_slugify_is_stable_and_url_safe():
    assert service.slugify("Type 2 Diabetes") == "type-2-diabetes"
    assert service.slugify("!!!") == "landscape"


def test_get_landscape_seeds_ctgov_and_caches(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    calls = {"n": 0}

    def search(condition):
        calls["n"] += 1
        return [_study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),))]

    ls = service.get_landscape(store, "Type 2 Diabetes", search_pipeline=search)
    assert "Semaglutide" in ls.assets
    assert calls["n"] == 1
    # Second call is served from the store — no re-fetch.
    service.get_landscape(store, "Type 2 Diabetes", search_pipeline=search)
    assert calls["n"] == 1


def test_refresh_clears_stale_cache_and_reseeds(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # First seed carries a stale/off-target asset (the pre-fix query.term era).
    stale = _search([_study(nct="NCT1", interventions=(("DRUG", "Karolinska Cocktail"),))])
    ls = service.get_landscape(store, "Obesity", search_pipeline=stale)
    assert "Karolinska Cocktail" in ls.assets

    # A refresh drops the cache and re-pulls from the (now clean) search.
    fresh = _search([_study(nct="NCT2", interventions=(("DRUG", "Semaglutide"),))])
    refreshed = service.get_landscape(
        store, "Obesity", search_pipeline=fresh, refresh=True
    )
    assert "Semaglutide" in refreshed.assets
    assert "Karolinska Cocktail" not in refreshed.assets


def test_as_of_reconstructs_earlier_pipeline(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    study = _study(
        nct="NCT1",
        phases=("PHASE3",),
        start="2015-03",
        interventions=(("DRUG", "Semaglutide"),),
    )
    service.get_landscape(store, "T2D", search_pipeline=_search([study]))
    # Before the 2015 start there is nothing yet.
    early = service.get_landscape(store, "T2D", as_of="2014-01-01")
    assert early.cells == []


def test_ingest_adds_announcement_events_to_the_matrix(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    service.get_landscape(
        store, "T2D", search_pipeline=_search([_study(interventions=(("DRUG", "Semaglutide"),))])
    )
    client = _StubClient(
        [_ext(asset_name="Tirzepatide", indication="Type 2 Diabetes", phase="Phase 3")]
    )
    added = service.ingest_to_landscape(
        store, "T2D", "Lilly announces...", "PR:lilly", llm_client=client
    )
    assert len(added) == 1
    ls = service.get_landscape(store, "T2D")
    assert "Tirzepatide" in ls.assets


def test_link_surfaces_evidence_badge(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # A saved review to link to.
    import math

    q = Question(
        id="glp1-mace",
        text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )
    pool = PoolResult(
        measure=EffectMeasure.HR, engine="python", k=6,
        estimate=0.86, ci_low=0.79, ci_high=0.93, ci_method=CIMethod.WALD,
        estimate_log=math.log(0.86), se_log=0.04, ci_low_log=-0.23, ci_high_log=-0.07,
        tau2=0.0, i2=10.0, q=1.0, q_p=0.9,
    )
    store.save_snapshot(ReviewResult(question=q, pool=pool))

    study = _study(
        nct="NCT1", conditions=("Type 2 Diabetes",), interventions=(("DRUG", "Semaglutide"),)
    )
    service.get_landscape(store, "Type 2 Diabetes", search_pipeline=_search([study]))
    service.link_review(store, "Type 2 Diabetes", "Semaglutide", "Type 2 Diabetes", "glp1-mace")

    ls = service.get_landscape(store, "Type 2 Diabetes")
    cell = next(c for c in ls.cells if c.asset_name == "Semaglutide")
    assert cell.question_id == "glp1-mace"
    assert cell.evidence is not None
    assert cell.evidence.state == "pooled"
    assert cell.evidence.conclusion == "significant reduction"


def test_live_search_failure_degrades_gracefully(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)

    def boom(condition):
        raise RuntimeError("403 Forbidden from CT.gov")

    ls = service.get_landscape(store, "T2D", search_pipeline=boom)
    assert ls.cells == []  # no crash
    assert any("unavailable" in n for n in ls.notes)


def test_asset_timeline_filters_by_name(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT2", interventions=(("DRUG", "Tirzepatide"),)),
    ]
    service.get_landscape(store, "T2D", search_pipeline=_search(studies))
    timeline = service.asset_timeline(store, "T2D", "Semaglutide")
    assert timeline and all(e.asset_name == "Semaglutide" for e in timeline)
