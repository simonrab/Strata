"""The optional matplotlib PNG forest plot (`--plot`).

Rendering is not asserted pixel-by-pixel — fonts and anti-aliasing vary by
machine. The contract is: a valid, non-empty PNG file appears where asked. That
plus the ASCII forest (exercised in test_cli_render) covers the plot surface.
"""

import json
from pathlib import Path

import pytest

from livemeta.cli import plot as plot_mod
from livemeta.cli.app import main
from tests.glp1_fixtures import GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.store import SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _fetch(nct_id: str) -> dict:
    return json.loads((FIXTURES / f"{nct_id}.json").read_text())


@pytest.fixture(scope="module")
def pool():
    return run_review_collect(GLP1_MACE_QUESTION, _fetch).pool


def test_write_forest_png_produces_a_valid_png(pool, tmp_path):
    out = tmp_path / "forest.png"
    plot_mod.write_forest_png(pool, str(out))
    assert out.exists()
    data = out.read_bytes()
    assert len(data) > 0
    assert data.startswith(_PNG_MAGIC)


def test_write_forest_png_highlights_without_error(pool, tmp_path):
    out = tmp_path / "forest_hl.png"
    plot_mod.write_forest_png(pool, str(out), highlight={pool.studies[-1].study_id})
    assert out.read_bytes().startswith(_PNG_MAGIC)


def test_run_plot_flag_writes_png(tmp_path):
    out = tmp_path / "run.png"
    main(
        argv=["run", "--question-text", GLP1_MACE_QUESTION.text, "--plot", str(out)],
        fetch_study=_fetch,
        store=SnapshotStore(tmp_path),
        # The parsed question already carries its trials, so no discovery/network.
        parse=lambda _t: GLP1_MACE_QUESTION,
    )
    assert out.read_bytes().startswith(_PNG_MAGIC)
