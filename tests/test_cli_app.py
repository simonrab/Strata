"""The CLI argparse surface, driven offline.

Every test calls `main(argv=[...], fetch_study=_fetch, store=SnapshotStore(tmp))`
so the process is hermetic and network-free, and asserts on the returned exit
code, the captured stdout/stderr, and the store side effects. The wiring mirrors
the FastAPI endpoints, so these are parity checks against `test_api.py` /
`test_mcp_server.py`.
"""

import json
from pathlib import Path

import pytest

from livemeta.cli.app import main
from tests.glp1_fixtures import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct_id: str) -> dict:
    return json.loads((FIXTURES / f"{nct_id}.json").read_text())


class _SearchClient:
    def search_studies(self, query, page_size=1000, interventional_only=False):
        return [{"nct_id": nct, "title": nct} for nct in GLP1_CVOT_TRIALS]

    def search_agent_studies(self, intervention, term=None, page_size=1000, **kwargs):
        return [{"nct_id": nct, "title": nct} for nct in GLP1_CVOT_TRIALS]


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(tmp_path)


def _seed7(store):
    q7 = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:7]})
    store.save_snapshot(run_review_collect(q7, _fetch))


# --- argparse ---------------------------------------------------------------


def test_no_command_is_a_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(argv=[])
    assert exc.value.code == 2


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv=["--help"])
    assert exc.value.code == 0
    assert "livemeta" in capsys.readouterr().out


# --- run --------------------------------------------------------------------


def test_run_demo_reports_and_saves(store, capsys):
    code = main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    out = capsys.readouterr().out
    assert code == 0
    assert "0.86" in out
    assert store.list_versions("glp1-mace") == [1]


def test_run_demo_json_is_clean(store, capsys):
    code = main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text, "--json"], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    captured = capsys.readouterr()
    assert code == 0
    doc = json.loads(captured.out)  # stdout is a single JSON document
    assert round(doc["pool"]["estimate"], 2) == 0.86


def test_run_demo_no_save_persists_nothing(store):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text, "--no-save"], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    assert store.list_versions("glp1-mace") == []


def test_run_abstains_with_exit_4(store):
    # One trial cannot be pooled — an honest abstention, exit 4.
    code = main(
        argv=["run", "--question-text", "x"],
        fetch_study=_fetch,
        store=store,
        parse=lambda _t: GLP1_MACE_QUESTION.model_copy(
            update={"trial_ids": GLP1_CVOT_TRIALS[:1]}
        ),
    )
    assert code == 4


# --- read commands ----------------------------------------------------------


def test_report_unknown_id_is_exit_5(store, capsys):
    code = main(argv=["report", "nope"], store=store)
    assert code == 5


def test_report_after_run(store, capsys):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    capsys.readouterr()
    code = main(argv=["report", "glp1-mace"], store=store)
    assert code == 0
    assert "0.86" in capsys.readouterr().out


def test_history_lists_versions(store, capsys):
    _seed7(store)
    code = main(argv=["history", "glp1-mace"], store=store)
    assert code == 0
    assert "1" in capsys.readouterr().out


def test_list_shows_saved_reviews(store, capsys):
    _seed7(store)
    code = main(argv=["list"], store=store)
    assert code == 0
    assert "glp1-mace" in capsys.readouterr().out


def test_search_offline(store, capsys):
    code = main(
        argv=["search", "--intervention", "GLP-1", "--outcome", "MACE"],
        search_client=_SearchClient(),
    )
    assert code == 0
    assert "NCT01147250" in capsys.readouterr().out


# --- living -----------------------------------------------------------------


def test_update_adds_eighth_trial(store, capsys):
    _seed7(store)
    code = main(
        argv=["update", "glp1-mace", GLP1_CVOT_TRIALS[7]],
        fetch_study=_fetch,
        store=store,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "8" in out
    assert GLP1_CVOT_TRIALS[7] in out
    assert store.list_versions("glp1-mace") == [1, 2]


def test_update_unknown_id_is_exit_5(store):
    code = main(argv=["update", "nope", "NCT1"], fetch_study=_fetch, store=store)
    assert code == 5


def test_check_updates_returns_only_new(store, capsys):
    _seed7(store)
    code = main(
        argv=["check-updates", "glp1-mace"],
        store=store,
        search_client=_SearchClient(),
    )
    assert code == 0
    assert GLP1_CVOT_TRIALS[7] in capsys.readouterr().out


# --- HITL decisions ---------------------------------------------------------


def test_decision_flag_drops_a_trial_and_bumps_version(store, capsys):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    capsys.readouterr()
    code = main(
        argv=["decision", "glp1-mace", GLP1_CVOT_TRIALS[0], "flagged", "--reason", "unclear arm", "--json"],
        store=store,
    )
    assert code == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["pool"]["k"] == 7
    assert GLP1_CVOT_TRIALS[0] not in {s["study_id"] for s in doc["pool"]["studies"]}
    assert store.list_versions("glp1-mace") == [1, 2]


def test_rob_decision_records_signoff(store, capsys):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    capsys.readouterr()
    code = main(
        argv=["rob-decision", "glp1-mace", GLP1_CVOT_TRIALS[0], "D1", "--reason", "ok"],
        store=store,
    )
    assert code == 0
    assert store.load_rob_decisions("glp1-mace")
    assert store.list_versions("glp1-mace") == [1, 2]


def test_screening_decision_reruns_and_saves(store, capsys):
    main(argv=["run", "--question-text", GLP1_MACE_QUESTION.text], fetch_study=_fetch, store=store, search_client=_SearchClient(), parse=_parse)
    capsys.readouterr()
    code = main(
        argv=["screening-decision", "glp1-mace", GLP1_CVOT_TRIALS[0], "included", "--reason", "keep"],
        fetch_study=_fetch,
        store=store,
    )
    assert code == 0
    assert store.load_screening_decisions("glp1-mace")
    assert store.list_versions("glp1-mace") == [1, 2]


def _parse(_text):
    # Stand in for the live PICO parser: the demo PICO with no trials, so the run
    # discovers through the injected search client (offline, deterministic).
    return GLP1_MACE_QUESTION.model_copy(update={"trial_ids": []})
