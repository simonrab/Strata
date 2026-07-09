"""v2 persistence (SQLite): subpop cache + approvals cache + global links."""

from livemeta.core.ci.schema import RegulatoryApproval, SubPopulation
from livemeta.core.store import SnapshotStore


def test_subpop_cache_round_trip_and_upsert(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    assert store.load_subpops(["NCT1"]) == {}
    store.save_subpop("NCT1", SubPopulation(base_indication="Obesity", comorbidities=["ckd"]))
    got = store.load_subpops(["NCT1", "NCT2"])
    assert set(got) == {"NCT1"}
    assert got["NCT1"].comorbidities == ["ckd"]
    # upsert
    store.save_subpop("NCT1", SubPopulation(base_indication="Obesity", comorbidities=["t2d"]))
    assert store.load_subpops(["NCT1"])["NCT1"].comorbidities == ["t2d"]


def test_approvals_cache_round_trip_by_drug(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    assert store.load_approvals("semaglutide") == []
    store.save_approvals([
        RegulatoryApproval(drug="semaglutide", application_number="NDA1", brand_names=["OZEMPIC"]),
        RegulatoryApproval(drug="semaglutide", application_number="NDA2", brand_names=["RYBELSUS"]),
    ])
    got = store.load_approvals("semaglutide")
    assert [a.application_number for a in got] == ["NDA1", "NDA2"]
    assert store.load_approvals("tirzepatide") == []


def test_load_all_links_spans_landscapes(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    store.save_link("obesity", "Semaglutide", "Obesity", "sema-mace")
    store.save_link("t2d", "Tirzepatide", "Type 2 Diabetes", "tirz-mace")
    all_links = store.load_all_links()
    assert all_links[("Semaglutide", "Obesity")] == "sema-mace"
    assert all_links[("Tirzepatide", "Type 2 Diabetes")] == "tirz-mace"
