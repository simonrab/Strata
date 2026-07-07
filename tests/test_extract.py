"""Structured extraction from ClinicalTrials.gov v2 results.

For time-to-event MACE, CT.gov reports the hazard ratio with its CI in the
outcome measure's `analyses` block. We take it straight from the structured
field — with provenance — never re-deriving it. If it is not clearly present,
return a flag, not a guess.
"""

import json
from pathlib import Path

import pytest

from livemeta.core.extract import extract_hr

FIXTURES = Path(__file__).parent / "fixtures"


def _load(nct):
    return json.loads((FIXTURES / f"{nct}.json").read_text())


def test_extract_leader_primary_mace_hr():
    ext = extract_hr(_load("NCT01179048"))
    assert ext.study_id == "NCT01179048"
    assert not ext.flagged
    assert ext.hr == pytest.approx(0.868)
    assert ext.ci_low == pytest.approx(0.778)
    assert ext.ci_high == pytest.approx(0.968)
    # Effect point is ready to pool and carries provenance.
    assert ext.point is not None
    assert ext.point.yi == pytest.approx(-0.1416, abs=1e-3)
    assert ext.provenance and "0.868" in ext.provenance[0].snippet
    assert ext.provenance[0].trial_id == "NCT01179048"


def test_extract_sustain6_primary_mace_hr():
    ext = extract_hr(_load("NCT01720446"))
    assert not ext.flagged
    assert ext.hr == pytest.approx(0.74)
    assert (ext.ci_low, ext.ci_high) == (pytest.approx(0.58), pytest.approx(0.95))


def test_missing_hr_is_flagged_not_guessed():
    empty = {
        "protocolSection": {"identificationModule": {"nctId": "NCT00000000"}},
        "resultsSection": {"outcomeMeasuresModule": {"outcomeMeasures": []}},
    }
    ext = extract_hr(empty)
    assert ext.flagged
    assert ext.point is None
    assert ext.hr is None
    assert ext.flag_reason
