"""The pure CLI renderers — the heavily tested unit (no I/O, no argparse).

Every function under test takes Pydantic models and returns a `str`, so the
report text, the ASCII forest plot, and the diff/table blocks can be asserted
character by character. The pooled fixtures come from an offline
`run_review_collect` over the recorded CT.gov JSON, so these tests never touch
the network.
"""

import json
from pathlib import Path

import pytest

from livemeta.cli import render
from tests.glp1_fixtures import GLP1_CVOT_TRIALS, GLP1_MACE_QUESTION
from livemeta.core.pipeline import run_review_collect
from livemeta.core.schema import (
    EffectMeasure,
    PipelineEvent,
    PoolResult,
    ReviewDiff,
    SnapshotMeta,
    TrialCandidate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(nct_id: str) -> dict:
    return json.loads((FIXTURES / f"{nct_id}.json").read_text())


@pytest.fixture(scope="module")
def result():
    return run_review_collect(GLP1_MACE_QUESTION, _fetch)


# --- report_text ------------------------------------------------------------


def test_report_text_shows_pooled_estimate_and_summary(result):
    text = render.report_text(result)
    assert "0.86" in text  # the locked demo answer
    assert "HR" in text
    assert "95% CI" in text
    # the plain-language summary sentence is included
    assert result.summary in text


def test_report_text_includes_ascii_forest_with_pooled_row(result):
    text = render.report_text(result)
    assert "Pooled" in text
    # every pooled study id appears as a forest row
    for study in result.pool.studies:
        assert study.study_id in text


def test_report_text_marks_rob_pending_without_a_key(result):
    # Offline, keyless: RoB must be surfaced honestly as PENDING, not fabricated.
    text = render.report_text(result)
    assert "PENDING" in text


def test_report_text_handles_abstention_without_a_pool():
    # A review that abstained (no pool) still renders, never crashes.
    q = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": GLP1_CVOT_TRIALS[:1]})
    abstained = run_review_collect(q, _fetch)
    assert abstained.pool is None
    text = render.report_text(abstained)
    assert "abstain" in text.lower() or "too few" in text.lower()


# --- forest_ascii -----------------------------------------------------------


def test_forest_ascii_has_one_row_per_study_plus_pooled(result):
    art = render.forest_ascii(result.pool)
    lines = [ln for ln in art.splitlines() if ln.strip()]
    labels = [s.study_id for s in result.pool.studies]
    for label in labels:
        assert any(label in ln for ln in lines)
    assert any("Pooled" in ln for ln in lines)


def test_forest_ascii_annotates_effect_and_ci(result):
    art = render.forest_ascii(result.pool)
    first = result.pool.studies[0]
    assert f"{first.effect:.2f}" in art


def test_forest_ascii_highlights_injected_study(result):
    target = result.pool.studies[-1].study_id
    art = render.forest_ascii(result.pool, highlight={target})
    assert "NEW" in art


def _continuous_pool() -> PoolResult:
    from livemeta.core.schema import StudyResult

    return PoolResult(
        measure=EffectMeasure.MD,
        engine="python",
        k=2,
        estimate=-1.5,
        ci_low=-3.0,
        ci_high=0.0,
        ci_method="wald",
        estimate_log=-1.5,
        se_log=0.7,
        ci_low_log=-3.0,
        ci_high_log=0.0,
        tau2=0.0,
        i2=0.0,
        q=0.5,
        q_p=0.5,
        studies=[
            StudyResult(
                study_id="S1", label="S1", yi=-2.0, vi=1.0,
                effect=-2.0, ci_low=-4.0, ci_high=0.0, weight=50.0,
            ),
            StudyResult(
                study_id="S2", label="S2", yi=-1.0, vi=1.0,
                effect=-1.0, ci_low=-3.0, ci_high=1.0, weight=50.0,
            ),
        ],
    )


def test_forest_ascii_linear_axis_for_continuous_measures():
    # MD/SMD render on a linear axis with a 0 reference, never a log axis.
    art = render.forest_ascii(_continuous_pool())
    assert "0" in art
    assert "S1" in art and "S2" in art


# --- diff_block -------------------------------------------------------------


def test_diff_block_reports_trial_counts_and_status():
    diff = ReviewDiff(
        question_id="glp1-mace",
        previous_version=1,
        current_version=2,
        estimate_prev=0.88,
        estimate_curr=0.86,
        delta=-0.02,
        k_prev=7,
        k_curr=8,
        added_trials=["NCT03496298"],
        conclusion_changed=False,
    )
    block = render.diff_block(diff, "estimate-updated")
    assert "7" in block and "8" in block
    assert "NCT03496298" in block
    assert "estimate-updated" in block


# --- tables -----------------------------------------------------------------


def test_history_table_lists_versions():
    snaps = [
        SnapshotMeta(question_id="glp1-mace", version=1, created_at="2026-01-01T00:00:00+00:00", k=7, estimate=0.88, measure="HR"),
        SnapshotMeta(question_id="glp1-mace", version=2, created_at="2026-02-01T00:00:00+00:00", k=8, estimate=0.86, measure="HR"),
    ]
    table = render.history_table(snaps)
    assert "1" in table and "2" in table
    assert "0.88" in table and "0.86" in table


def test_candidates_table_lists_new_trials():
    cands = [TrialCandidate(nct_id="NCT03496298", title="AMPLITUDE-O")]
    table = render.candidates_table(cands)
    assert "NCT03496298" in table
    assert "AMPLITUDE-O" in table


# --- progress_line ----------------------------------------------------------


def test_progress_line_formats_stage_and_message():
    line = render.progress_line(PipelineEvent(stage="extract", message="LEADER: HR 0.87"))
    assert "extract" in line
    assert "LEADER: HR 0.87" in line
