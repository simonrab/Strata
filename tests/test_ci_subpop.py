"""Sub-population extraction: Claude reads eligibility, code degrades safely."""

from livemeta.core.ci import subpop
from livemeta.core.ci.subpop import extract_sub_population


class _StubParsed:
    def __init__(self, output):
        self.parsed_output = output


class _StubMessages:
    def __init__(self, output):
        self._output = output

    def parse(self, **kwargs):
        return _StubParsed(self._output)


class _StubClient:
    def __init__(self, read):
        self.messages = _StubMessages(read)


def _study(criteria="Adults with BMI>=30 and established cardiovascular disease.",
           condition="Obesity"):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT1"},
            "conditionsModule": {"conditions": [condition]},
            "eligibilityModule": {
                "minimumAge": "45 Years", "sex": "ALL",
                "eligibilityCriteria": criteria,
            },
        }
    }


def _read(**kw):
    base = dict(found=True, confidence="high", source_snippet="quote",
               base_indication="Obesity")
    base.update(kw)
    return subpop._SubPopRead(**base)


def test_high_confidence_read_structures_subpopulation():
    client = _StubClient(_read(comorbidities=["established_cvd"], age_min=45, sex="ALL"))
    sp = extract_sub_population(_study(), llm_client=client)
    assert sp.base_indication == "Obesity"
    assert sp.comorbidities == ["established_cvd"]
    assert sp.age_min == 45
    assert sp.provenance[0].snippet == "quote"


def test_low_confidence_degrades_to_base_indication():
    client = _StubClient(_read(confidence="low", comorbidities=["established_cvd"]))
    sp = extract_sub_population(_study(), llm_client=client)
    assert sp.base_indication == "Obesity"
    assert sp.comorbidities == []  # not fabricated


def test_not_found_degrades_to_base_indication():
    client = _StubClient(_read(found=False, comorbidities=["ckd"]))
    sp = extract_sub_population(_study(), llm_client=client)
    assert sp.comorbidities == []


def test_keyless_returns_base_indication_only(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sp = extract_sub_population(_study())  # no client, no key
    assert sp.base_indication == "Obesity"
    assert sp.comorbidities == []


def test_no_eligibility_text_degrades_without_calling_model():
    study = _study(criteria="")
    # even with a client, absent eligibility -> base only
    client = _StubClient(_read(comorbidities=["should_not_appear"]))
    sp = extract_sub_population(study, llm_client=client)
    assert sp.comorbidities == []
