"""FastAPI surface — REST run endpoint and the WebSocket event stream.

Driven offline: the CT.gov fetch dependency is overridden with recorded fixtures.
"""

import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from livemeta.api.app import (
    app,
    get_fetch_study,
    get_parse,
    get_search_client,
    get_store,
)
from tests import glp1_fixtures as demo
from livemeta.core.schema import (
    PICO,
    CIMethod,
    EffectMeasure,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _review_with_estimate(estimate: float, ci_low: float, ci_high: float) -> ReviewResult:
    """A glp1-mace ReviewResult with a chosen pooled estimate, for status tests."""
    pool = PoolResult(
        measure=EffectMeasure.HR,
        engine="python",
        k=8,
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=CIMethod.HKSJ,
        estimate_log=math.log(estimate),
        se_log=0.04,
        ci_low_log=math.log(ci_low),
        ci_high_log=math.log(ci_high),
        tau2=0.004,
        i2=30.0,
        q=10.0,
        q_p=0.2,
    )
    return ReviewResult(question=demo.GLP1_MACE_QUESTION, pool=pool)


def _fixture_fetch():
    def fetch(nct: str) -> dict:
        return json.loads((FIXTURES / f"{nct}.json").read_text())

    return fetch


def _stub_parse():
    def parse(text: str) -> Question:
        return Question(
            id="q-novel",
            text=text,
            pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
            trial_ids=["NCT00000001"],
        )

    return parse


app.dependency_overrides[get_fetch_study] = _fixture_fetch
client = TestClient(app)


@pytest.fixture()
def store(tmp_path):
    """Isolated per-test snapshot store."""
    s = SnapshotStore(tmp_path)
    app.dependency_overrides[get_store] = lambda: s
    yield s
    app.dependency_overrides.pop(get_store, None)


def test_run_endpoint_returns_pooled_result():
    from livemeta.api.app import get_discovery

    # A question with no trial_ids is discovered live; drive discovery offline with
    # the fixture set so the run is deterministic and network-free.
    app.dependency_overrides[get_discovery] = lambda: (
        lambda _pico: list(demo.GLP1_CVOT_TRIALS)
    )
    try:
        r = client.post(
            "/api/reviews/run", json=demo.GLP1_MACE_DISCOVER.model_dump(mode="json")
        )
    finally:
        app.dependency_overrides.pop(get_discovery, None)
    assert r.status_code == 200
    body = r.json()
    assert round(body["pool"]["estimate"], 2) == 0.86
    assert len(body["extractions"]) == 8
    assert body["pool"]["ci_method"] == "hksj"


def test_ws_streams_pipeline_events(store):
    from livemeta.api.app import get_discovery

    # A question with no trial_ids is discovered live; drive discovery offline with
    # the fixture set so the stream stays deterministic.
    app.dependency_overrides[get_discovery] = lambda: (
        lambda _pico: list(demo.GLP1_CVOT_TRIALS)
    )
    try:
        with client.websocket_connect("/ws/review") as ws:
            ws.send_json({"question": demo.GLP1_MACE_DISCOVER.model_dump(mode="json")})
            stages = []
            while True:
                ev = ws.receive_json()
                stages.append(ev["stage"])
                if ev["stage"] == "done":
                    assert "reduced" in ev["message"].lower()
                    break
    finally:
        app.dependency_overrides.pop(get_discovery, None)
    assert stages[0] == "parse"
    assert "search" in stages  # a real discovery stage ran
    assert "pool" in stages
    assert stages.count("extract") == 8
    # A completed run is persisted so it appears on the dashboard.
    assert store.load_latest("glp1-mace") is not None


def test_parse_endpoint_returns_a_question():
    app.dependency_overrides[get_parse] = _stub_parse
    try:
        r = client.post("/api/parse", json={"text": "novel question?"})
    finally:
        app.dependency_overrides.pop(get_parse, None)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q-novel"
    assert body["trial_ids"] == ["NCT00000001"]


def _demo_review():
    from livemeta.core.pipeline import run_review_collect

    return run_review_collect(demo.GLP1_MACE_QUESTION, _fixture_fetch())


def test_list_reviews_reflects_saved_snapshots(store):
    store.save_snapshot(_demo_review())
    r = client.get("/api/reviews")
    assert r.status_code == 200
    rows = r.json()
    ids = [row["question_id"] for row in rows]
    assert "glp1-mace" in ids
    row = next(row for row in rows if row["question_id"] == "glp1-mace")
    assert round(row["estimate"], 2) == 0.86
    assert row["k"] == 8


def test_list_reviews_status_is_estimate_updated_when_estimate_moves(store):
    store.save_snapshot(_review_with_estimate(0.88, 0.81, 0.96))  # v1
    store.save_snapshot(_review_with_estimate(0.86, 0.79, 0.94))  # v2, still significant
    row = next(r for r in client.get("/api/reviews").json() if r["question_id"] == "glp1-mace")
    assert row["status"] == "estimate-updated"


def test_list_reviews_status_is_conclusion_moved_when_significance_flips(store):
    store.save_snapshot(_review_with_estimate(0.86, 0.79, 0.94))  # v1, significant
    store.save_snapshot(_review_with_estimate(0.92, 0.84, 1.01))  # v2, CI now crosses 1
    row = next(r for r in client.get("/api/reviews").json() if r["question_id"] == "glp1-mace")
    assert row["status"] == "conclusion-moved"


def test_list_reviews_status_is_unchanged_with_a_single_version(store):
    store.save_snapshot(_review_with_estimate(0.86, 0.79, 0.94))
    row = next(r for r in client.get("/api/reviews").json() if r["question_id"] == "glp1-mace")
    assert row["status"] == "unchanged"


def test_get_review_returns_latest_and_404s_when_missing(store):
    store.save_snapshot(_demo_review())
    r = client.get("/api/reviews/glp1-mace")
    assert r.status_code == 200
    assert len(r.json()["extractions"]) == 8

    assert client.get("/api/reviews/does-not-exist").status_code == 404


def _seed_seven(store):
    """Persist a 7-trial GLP-1 baseline (v1) so an inject can add the eighth."""
    from livemeta.core.pipeline import run_review_collect

    q7 = demo.GLP1_MACE_QUESTION.model_copy(
        update={"trial_ids": demo.GLP1_CVOT_TRIALS[:7]}
    )
    store.save_snapshot(run_review_collect(q7, _fixture_fetch()))


def test_update_endpoint_adds_trial_and_returns_diff(store):
    _seed_seven(store)
    r = client.post(
        "/api/reviews/glp1-mace/update",
        json={"new_trial_id": demo.GLP1_CVOT_TRIALS[7]},
    )
    assert r.status_code == 200
    diff = r.json()
    assert diff["k_curr"] == 8
    assert demo.GLP1_CVOT_TRIALS[7] in diff["added_trials"]
    assert isinstance(diff["conclusion_changed"], bool)
    assert store.list_versions("glp1-mace") == [1, 2]


def test_update_endpoint_404_when_no_review(store):
    r = client.post(
        "/api/reviews/does-not-exist/update", json={"new_trial_id": "NCT00000001"}
    )
    assert r.status_code == 404


class _FakeSearchClient:
    def __init__(self, nct_ids):
        self._ids = list(nct_ids)

    def search_studies(self, query, page_size=1000, interventional_only=False):
        return [{"nct_id": nct, "title": nct} for nct in self._ids]

    def search_agent_studies(self, intervention, term=None, page_size=1000, **kwargs):
        return [{"nct_id": nct, "title": nct} for nct in self._ids]


def test_check_updates_endpoint_returns_only_new_trials(store):
    _seed_seven(store)
    # Re-search surfaces the 7 already-pooled plus the held-out eighth.
    app.dependency_overrides[get_search_client] = lambda: _FakeSearchClient(
        demo.GLP1_CVOT_TRIALS
    )
    try:
        r = client.post("/api/reviews/glp1-mace/check-updates")
    finally:
        app.dependency_overrides.pop(get_search_client, None)

    assert r.status_code == 200
    ids = [c["nct_id"] for c in r.json()]
    assert ids == [demo.GLP1_CVOT_TRIALS[7]]  # only the genuinely-new one


def test_check_updates_endpoint_404_when_no_review(store):
    app.dependency_overrides[get_search_client] = lambda: _FakeSearchClient([])
    try:
        r = client.post("/api/reviews/does-not-exist/check-updates")
    finally:
        app.dependency_overrides.pop(get_search_client, None)
    assert r.status_code == 404


def test_screening_decision_excludes_then_readmits_a_trial(store):
    from livemeta.core.pipeline import run_review_collect

    store.save_snapshot(run_review_collect(demo.GLP1_MACE_QUESTION, _fixture_fetch()))
    target = demo.GLP1_CVOT_TRIALS[0]

    # Override: exclude one trial at screening — the review re-runs and the pool drops.
    r = client.post(
        "/api/reviews/glp1-mace/screening/decision",
        json={"study_id": target, "decision": "excluded", "reason": "wrong population"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pool"]["k"] == 7
    dec = next(d for d in body["screening"] if d["study_id"] == target)
    assert dec["decision"] == "excluded"
    assert dec["confirmed"] is True
    assert dec["by_claude"] is False
    assert target not in {s["study_id"] for s in body["pool"]["studies"]}

    # Override again: re-admit it — a screened-out trial is re-fetched and re-pooled.
    r2 = client.post(
        "/api/reviews/glp1-mace/screening/decision",
        json={"study_id": target, "decision": "included"},
    )
    assert r2.status_code == 200
    assert r2.json()["pool"]["k"] == 8


def test_screening_decision_404_when_no_review(store):
    r = client.post(
        "/api/reviews/does-not-exist/screening/decision",
        json={"study_id": "NCT00000001", "decision": "excluded"},
    )
    assert r.status_code == 404


def test_history_endpoint_lists_snapshot_metas(store):
    store.save_snapshot(_review_with_estimate(0.88, 0.81, 0.96))
    store.save_snapshot(_review_with_estimate(0.86, 0.79, 0.94))
    r = client.get("/api/reviews/glp1-mace/history")
    assert r.status_code == 200
    metas = r.json()
    assert [m["version"] for m in metas] == [1, 2]
    assert all(m["created_at"] for m in metas)
    assert round(metas[1]["estimate"], 2) == 0.86
    # An unknown review has no history rather than a 404.
    assert client.get("/api/reviews/nope/history").json() == []


def test_version_endpoint_returns_past_result_and_404s(store):
    store.save_snapshot(_review_with_estimate(0.88, 0.81, 0.96))
    r = client.get("/api/reviews/glp1-mace/versions/1")
    assert r.status_code == 200
    assert r.json()["question"]["id"] == "glp1-mace"
    assert client.get("/api/reviews/glp1-mace/versions/99").status_code == 404


def test_decision_endpoint_flags_trial_and_repools(store):
    review = _demo_review()
    store.save_snapshot(review)
    target = review.extractions[0].study_id

    r = client.post(
        "/api/reviews/glp1-mace/decision",
        json={"study_id": target, "decision": "flagged", "reason": "unclear arm"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pool"]["k"] == 7
    pooled_ids = {s["study_id"] for s in body["pool"]["studies"]}
    assert target not in pooled_ids
    # Decision persisted + a new snapshot version created (the audit trail).
    assert any(d.study_id == target for d in store.load_decisions("glp1-mace"))
    assert store.list_versions("glp1-mace") == [1, 2]


def test_diversity_decision_endpoint_lifts_gate_and_pools(store):
    from livemeta.core.pipeline import run_review_collect
    from livemeta.core.schema import DiversityAssessment

    # A review withheld at the homogeneity gate: no pool, diversity requires
    # confirmation. Confirming it must pool the same extractions.
    withheld = run_review_collect(
        demo.GLP1_MACE_QUESTION.model_copy(
            update={"trial_ids": ["NCT01179048", "NCT01720446"]}
        ),
        _fixture_fetch(),
    )
    withheld.pool = None
    withheld.diversity = DiversityAssessment(
        i2=85.0, i2_band="substantial", requires_confirmation=True
    )
    store.save_snapshot(withheld)

    r = client.post(
        "/api/reviews/glp1-mace/diversity/decision",
        json={"reason": "clinically combinable"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pool"] is not None
    assert body["diversity"]["confirmed"] is True
    assert store.list_versions("glp1-mace") == [1, 2]


def test_diversity_decision_endpoint_404_when_no_review(store):
    r = client.post("/api/reviews/nope/diversity/decision", json={"reason": "x"})
    assert r.status_code == 404
