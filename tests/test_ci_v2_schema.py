"""v2 schema logic: source selection + sub-population clustering key."""

from livemeta.core.ci.schema import (
    FREE_TEXT_SOURCES,
    STRUCTURED_SOURCES,
    Source,
    SourceSelection,
    SubPopulation,
)
from livemeta.core.ci.schema import SourceType


def test_default_selection_is_structured_only():
    sel = SourceSelection.default()
    assert set(sel.enabled) == set(STRUCTURED_SOURCES)
    assert not sel.free_text_enabled
    assert sel.allows(Source.CTGOV)
    assert sel.allows(Source.OPENFDA)
    for s in FREE_TEXT_SOURCES:
        assert not sel.allows(s)


def test_from_param_parses_and_ignores_unknown():
    sel = SourceSelection.from_param("ctgov, announcement , bogus")
    assert set(sel.enabled) == {Source.CTGOV, Source.ANNOUNCEMENT}
    assert sel.free_text_enabled
    # empty / None -> default structured
    assert set(SourceSelection.from_param(None).enabled) == set(STRUCTURED_SOURCES)
    assert set(SourceSelection.from_param("").enabled) == set(STRUCTURED_SOURCES)


def test_allows_accepts_source_type_and_str():
    sel = SourceSelection.default()
    # DevelopmentEvent.source_type is a SourceType whose values align with Source
    assert sel.allows(SourceType.CTGOV)
    assert not sel.allows(SourceType.ANNOUNCEMENT)
    assert sel.allows("ctgov")
    assert not sel.allows("filing")


def test_subpopulation_signature_clusters_equivalent_targets():
    a = SubPopulation(
        base_indication="Obesity", age_min=45, comorbidities=["established_cvd"], sex="ALL"
    )
    b = SubPopulation(
        base_indication="obesity", age_min=45, comorbidities=["ESTABLISHED_CVD"], sex="all"
    )
    c = SubPopulation(base_indication="Obesity", comorbidities=["t2d"])
    assert a.signature() == b.signature()  # case/whitespace-insensitive
    assert a.signature() != c.signature()


def test_subpopulation_display_derived_when_no_label():
    sp = SubPopulation(base_indication="Obesity", comorbidities=["established CVD"], age_min=65)
    text = sp.display()
    assert "Obesity" in text and "established CVD" in text and "65" in text
