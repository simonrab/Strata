"""The market-intelligence chat: routing + grounded answers over the shared core.

Runs entirely offline via the deterministic keyword router and fake searches.
"""

from livemeta.core.ci import ask
from livemeta.core.ci.ask import MarketDeps
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


# --- routing (deterministic fallback) ---------------------------------------


def test_route_compare_pattern():
    q = ask.route("Compare tirzepatide and semaglutide")
    assert q.tool == "compare"
    assert q.assets == ["Tirzepatide", "Semaglutide"]


def test_route_vs_pattern():
    q = ask.route("tirzepatide vs semaglutide")
    assert q.tool == "compare" and len(q.assets) == 2


def test_route_changes_radar_moa():
    assert ask.route("what changed in obesity since January").tool == "changes"
    assert ask.route("upcoming readouts in obesity").tool == "radar"
    assert ask.route("group obesity by mechanism").tool == "moa"


def test_route_defaults_to_landscape():
    q = ask.route("map the obesity landscape")
    assert q.tool == "landscape"
    assert "obesity" in (q.condition or "").lower()


def test_llm_route_is_used_when_available():
    class _Stub:
        class messages:
            @staticmethod
            def parse(**kwargs):
                class R:
                    parsed_output = ask._RouteRead(tool="radar", condition="NASH", confidence="high")

                return R()

    q = ask.route("anything", llm_client=_Stub())
    assert q.tool == "radar" and q.condition == "NASH" and q.reason == "routed by Claude"


# --- answer (dispatch + grounded narrative) ---------------------------------


def _deps(studies):
    return MarketDeps(
        search_condition=lambda c: studies,
        search_asset=lambda a: [s for s in studies if a.lower() in _asset(s).lower()],
    )


def _asset(study):
    ivs = study["protocolSection"]["armsInterventionsModule"]["interventions"]
    return ivs[0]["name"]


def test_answer_landscape_renders_matrix_payload(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [_study(nct="NCT1", conditions=("Obesity",), interventions=(("DRUG", "Semaglutide"),))]
    a = ask.answer(store, "map the obesity landscape", deps=_deps(studies))
    assert a.tool == "landscape"
    assert "Semaglutide" in a.result["assets"]
    assert "asset" in a.narrative and a.suggestions


def test_answer_changes_routes_to_the_feed(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [_study(nct="NCT1", conditions=("Obesity",), interventions=(("DRUG", "Semaglutide"),))]
    a = ask.answer(store, "what changed in obesity since 2020", deps=_deps(studies))
    assert a.tool == "changes"
    assert "changes" in a.result  # the LandscapeDiff payload
    assert "move" in a.narrative


def test_answer_compare_is_operational(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Obesity",), interventions=(("DRUG", "Tirzepatide"),)),
        _study(nct="NCT2", conditions=("Obesity",), interventions=(("DRUG", "Semaglutide"),)),
    ]
    a = ask.answer(store, "compare tirzepatide and semaglutide", deps=_deps(studies))
    assert a.tool == "compare"
    # The narrative is operational — no pooled-evidence framing.
    assert "stage" in a.narrative and "timing" in a.narrative
    assert "pooled" not in a.narrative.lower()
