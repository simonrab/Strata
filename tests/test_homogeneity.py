"""Homogeneity / clinical-diversity gate (mandatory, CLAUDE.md).

Before pooling, surface clinical diversity (Claude-judged across the four PICO
domains) and statistical heterogeneity (I² band), and require human confirmation
before pooling unlike trials. The gate fires only on a deterministic I² band or
an explicit Claude "divergent" judgment — so keyless runs never force
confirmation, and the homogeneous GLP-1 demo pools straight through.
"""

import pytest

from livemeta.core.homogeneity import assess_diversity
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
)


def _question():
    return Question(
        id="q",
        text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )


def _pool(i2: float) -> PoolResult:
    return PoolResult(
        measure=EffectMeasure.HR,
        engine="python",
        k=4,
        estimate=0.86,
        ci_low=0.79,
        ci_high=0.94,
        ci_method=CIMethod.WALD,
        estimate_log=-0.15,
        se_log=0.04,
        ci_low_log=-0.23,
        ci_high_log=-0.06,
        tau2=0.01,
        i2=i2,
        q=10.0,
        q_p=0.02,
    )


class _StubParsed:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _StubLLM:
    def __init__(self, parsed):
        self._parsed = parsed

    class _Messages:
        def __init__(self, outer):
            self._outer = outer

        def parse(self, **kwargs):
            return _StubParsed(self._outer._parsed)

    @property
    def messages(self):
        return _StubLLM._Messages(self)


def test_low_i2_and_similar_pico_does_not_require_confirmation():
    from livemeta.core.homogeneity import _DiversityJudged

    judged = _DiversityJudged(
        population="similar",
        intervention="similar",
        comparator="similar",
        outcome="similar",
    )
    div = assess_diversity(
        _question(), [], [], _pool(20.0), llm_client=_StubLLM(judged)
    )
    assert div.requires_confirmation is False
    assert div.i2_band == "might not be important"


def test_substantial_i2_requires_confirmation():
    from livemeta.core.homogeneity import _DiversityJudged

    judged = _DiversityJudged(
        population="similar",
        intervention="similar",
        comparator="similar",
        outcome="similar",
    )
    div = assess_diversity(
        _question(), [], [], _pool(80.0), llm_client=_StubLLM(judged)
    )
    assert div.requires_confirmation is True
    assert div.i2_band == "substantial"


def test_divergent_population_requires_confirmation_despite_low_i2():
    from livemeta.core.homogeneity import _DiversityJudged

    judged = _DiversityJudged(
        population="divergent",
        intervention="similar",
        comparator="similar",
        outcome="similar",
        population_rationale="Trials enrolled very different populations.",
    )
    div = assess_diversity(
        _question(), [], [], _pool(15.0), llm_client=_StubLLM(judged)
    )
    assert div.requires_confirmation is True
    pop = next(d for d in div.domains if d.key == "population")
    assert pop.judgment == "divergent"


def test_keyless_does_not_fabricate_or_force_gate():
    # No client and no key: clinical domains are left un-judged (never fabricated),
    # and a non-substantial I² does not force confirmation.
    div = assess_diversity(_question(), [], [], _pool(30.0), llm_client=None)
    assert div.requires_confirmation is False
    assert div.domains  # four PICO domains present
    assert all(d.judgment == "not_assessed" for d in div.domains)
