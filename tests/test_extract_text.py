"""Claude-driven structured extraction from unstructured published text.

The safety-critical half of the second source: when a trial's effect data is
only in prose or a table, Claude *reads and structures* it into a binary 2x2,
continuous mean/SD/n, or ratio+CI — each with a provenance snippet quoting the
exact sentence or cell. Code does the arithmetic; low-confidence or keyless
reads are flagged, never invented. Tests use a stub client returning canned
structured output — the model and network are never hit.
"""

import pytest

from livemeta.core.extract import extract_from_text
from livemeta.core.extract_text import ExtractedEffect
from livemeta.core.schema import EffectMeasure


class _StubParsed:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _StubLLM:
    def __init__(self, parsed=None, raises=False):
        self._parsed = parsed
        self._raises = raises

    class _Messages:
        def __init__(self, outer):
            self._outer = outer

        def parse(self, **kwargs):
            if self._outer._raises:
                raise RuntimeError("model unavailable")
            return _StubParsed(self._outer._parsed)

    @property
    def messages(self):
        return _StubLLM._Messages(self)


def _doc(**over):
    base = {
        "id": "PMID:12345678",
        "source": "europepmc",
        "title": "A trial",
        "abstract": "The primary endpoint occurred in 40/500 vs 60/500.",
        "full_text": "",
        "tables": [],
    }
    base.update(over)
    return base


def test_extract_binary_from_abstract():
    parsed = ExtractedEffect(
        found=True,
        confidence="high",
        variant="binary",
        events_treatment=40,
        total_treatment=500,
        events_control=60,
        total_control=500,
        source_snippet="The primary endpoint occurred in 40/500 vs 60/500.",
    )
    ext = extract_from_text(_doc(), EffectMeasure.RR, llm_client=_StubLLM(parsed))
    assert not ext.flagged
    assert ext.binary is not None
    assert ext.binary.treatment.events == 40
    assert ext.point is not None
    assert ext.provenance and "40/500" in ext.provenance[0].snippet


def test_extract_continuous_from_table():
    parsed = ExtractedEffect(
        found=True,
        confidence="high",
        variant="continuous",
        mean_treatment=10.0,
        sd_treatment=2.0,
        n_treatment=50,
        mean_control=8.0,
        sd_control=2.5,
        n_control=50,
        source_snippet="Table 1: 10 (SD 2), n=50 vs 8 (SD 2.5), n=50",
    )
    ext = extract_from_text(_doc(), EffectMeasure.MD, llm_client=_StubLLM(parsed))
    assert not ext.flagged
    assert ext.continuous is not None
    assert ext.continuous.treatment.mean == pytest.approx(10.0)
    assert ext.point is not None


def test_extract_ratio_ci_from_abstract():
    parsed = ExtractedEffect(
        found=True,
        confidence="high",
        variant="ratio_ci",
        ratio=0.86,
        ci_low=0.79,
        ci_high=0.94,
        source_snippet="HR 0.86 (95% CI 0.79-0.94)",
    )
    ext = extract_from_text(_doc(), EffectMeasure.HR, llm_client=_StubLLM(parsed))
    assert not ext.flagged
    assert ext.hr == pytest.approx(0.86)
    assert ext.point is not None
    # The SE-from-CI conversion is logged as an assumption.
    assert "log_ratio_se_from_ci" in [a.code for a in ext.assumptions]


def test_continuous_sd_from_se_is_logged():
    # The model reports SEs; code recovers SD and logs the conversion.
    parsed = ExtractedEffect(
        found=True,
        confidence="high",
        variant="continuous",
        mean_treatment=10.0,
        se_treatment=0.283,
        n_treatment=50,
        mean_control=8.0,
        se_control=0.354,
        n_control=50,
        source_snippet="10 (SE 0.283) vs 8 (SE 0.354)",
    )
    ext = extract_from_text(_doc(), EffectMeasure.MD, llm_client=_StubLLM(parsed))
    assert not ext.flagged
    assert ext.continuous is not None
    assert "sd_from_se" in [a.code for a in ext.assumptions]


def test_low_confidence_is_flagged_not_invented():
    parsed = ExtractedEffect(
        found=True,
        confidence="low",
        variant="binary",
        events_treatment=40,
        total_treatment=500,
        events_control=60,
        total_control=500,
        source_snippet="unclear",
    )
    ext = extract_from_text(_doc(), EffectMeasure.RR, llm_client=_StubLLM(parsed))
    assert ext.flagged
    assert ext.point is None
    assert ext.flag_reason


def test_not_found_is_flagged():
    parsed = ExtractedEffect(found=False, confidence="low", variant="none", source_snippet="")
    ext = extract_from_text(_doc(), EffectMeasure.RR, llm_client=_StubLLM(parsed))
    assert ext.flagged
    assert ext.point is None


def test_keyless_is_flagged_not_invented():
    # No client and no key -> flagged, never fabricated.
    ext = extract_from_text(_doc(), EffectMeasure.RR, llm_client=None)
    assert ext.flagged
    assert ext.point is None
