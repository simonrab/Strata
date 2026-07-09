"""Structured extraction from ClinicalTrials.gov v2 results.

For time-to-event MACE, CT.gov reports the hazard ratio with its CI in the
outcome measure's `analyses` block. We take it straight from the structured
field — with provenance — never re-deriving it. If it is not clearly present,
return a flag, not a guess.
"""

import json
from pathlib import Path

import pytest

from livemeta.core.extract import extract, extract_binary, extract_continuous, extract_hr
from livemeta.core.schema import EffectMeasure

FIXTURES = Path(__file__).parent / "fixtures"


def _load(nct):
    return json.loads((FIXTURES / f"{nct}.json").read_text())


# --- Synthetic CT.gov-shaped results for binary / continuous outcomes -------
#
# The GLP-1 fixtures are hazard-ratio trials; binary 2x2 and continuous
# mean/SD outcomes are exercised against minimal hand-built records shaped like
# the CT.gov v2 outcomeMeasuresModule.


def _ctgov_binary(nct, a, n1, c, n2):
    """A COUNT_OF_PARTICIPANTS primary outcome: events per arm + denominators."""
    return {
        "protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}},
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "type": "PRIMARY",
                        "title": "Participants with the event",
                        "paramType": "COUNT_OF_PARTICIPANTS",
                        "groups": [
                            {"id": "OG000", "title": "Treatment"},
                            {"id": "OG001", "title": "Control"},
                        ],
                        "denoms": [
                            {
                                "units": "Participants",
                                "counts": [
                                    {"groupId": "OG000", "value": str(n1)},
                                    {"groupId": "OG001", "value": str(n2)},
                                ],
                            }
                        ],
                        "classes": [
                            {
                                "categories": [
                                    {
                                        "measurements": [
                                            {"groupId": "OG000", "value": str(a)},
                                            {"groupId": "OG001", "value": str(c)},
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        },
    }


def _ctgov_continuous(nct, m1, sd1, n1, m2, sd2, n2):
    """A MEAN primary outcome with STANDARD_DEVIATION dispersion + denominators."""
    return {
        "protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": nct}},
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "type": "PRIMARY",
                        "title": "Change in outcome score",
                        "paramType": "MEAN",
                        "dispersionType": "STANDARD_DEVIATION",
                        "groups": [
                            {"id": "OG000", "title": "Treatment"},
                            {"id": "OG001", "title": "Control"},
                        ],
                        "denoms": [
                            {
                                "units": "Participants",
                                "counts": [
                                    {"groupId": "OG000", "value": str(n1)},
                                    {"groupId": "OG001", "value": str(n2)},
                                ],
                            }
                        ],
                        "classes": [
                            {
                                "categories": [
                                    {
                                        "measurements": [
                                            {"groupId": "OG000", "value": str(m1), "spread": str(sd1)},
                                            {"groupId": "OG001", "value": str(m2), "spread": str(sd2)},
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        },
    }


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


# --- Binary (2x2) extraction ------------------------------------------------


def test_extract_binary_from_ctgov_2x2():
    ext = extract_binary(_ctgov_binary("NCT10000001", a=40, n1=500, c=60, n2=500))
    assert not ext.flagged
    assert ext.measure in (EffectMeasure.RR, EffectMeasure.OR)
    assert ext.binary is not None
    assert ext.binary.treatment.events == 40
    assert ext.binary.treatment.total == 500
    assert ext.binary.control.events == 60
    assert ext.binary.control.total == 500
    # Ready to pool, with provenance quoting the source counts.
    assert ext.point is not None
    assert ext.provenance and ext.provenance[0].trial_id == "NCT10000001"


def test_extract_binary_missing_counts_is_flagged():
    empty = {
        "protocolSection": {"identificationModule": {"nctId": "NCT10000009"}},
        "resultsSection": {"outcomeMeasuresModule": {"outcomeMeasures": []}},
    }
    ext = extract_binary(empty)
    assert ext.flagged
    assert ext.binary is None
    assert ext.point is None


# --- Continuous (mean/SD/n) extraction --------------------------------------


def test_extract_continuous_mean_sd_n():
    ext = extract_continuous(
        _ctgov_continuous("NCT10000002", m1=10.0, sd1=2.0, n1=50, m2=8.0, sd2=2.5, n2=50)
    )
    assert not ext.flagged
    assert ext.continuous is not None
    assert ext.continuous.treatment.mean == pytest.approx(10.0)
    assert ext.continuous.treatment.sd == pytest.approx(2.0)
    assert ext.continuous.treatment.n == 50
    assert ext.point is not None
    assert ext.provenance and ext.provenance[0].trial_id == "NCT10000002"


# --- Dispatch on measure ----------------------------------------------------


def test_extract_dispatches_on_measure():
    # HR path is byte-for-byte the existing extract_hr.
    hr = extract(_load("NCT01179048"), EffectMeasure.HR)
    assert hr.measure == EffectMeasure.HR
    assert hr.hr == pytest.approx(0.868)

    binary = extract(_ctgov_binary("NCT10000003", 40, 500, 60, 500), EffectMeasure.RR)
    assert binary.binary is not None

    cont = extract(
        _ctgov_continuous("NCT10000004", 10, 2, 50, 8, 2.5, 50), EffectMeasure.MD
    )
    assert cont.continuous is not None
