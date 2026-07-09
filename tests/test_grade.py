"""GRADE certainty: code derives what it can, Claude judges the rest.

Much of GRADE is computable from what we already have — risk of bias from RoB 2,
inconsistency from I², imprecision from the CI. Claude judges indirectness and
publication bias. These tests pin the deterministic derivation and the downgrade
arithmetic; the model is stubbed and never hit.
"""

import pytest

from livemeta.core import grade
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    GradeRating,
    PoolResult,
    Question,
    PICO,
    RobAssessment,
    RobJudgment,
)


def _pool(estimate, ci_low, ci_high, i2):
    import math

    return PoolResult(
        measure=EffectMeasure.HR,
        engine="python",
        k=8,
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=CIMethod.HKSJ,
        estimate_log=math.log(estimate),
        se_log=0.04,
        ci_low_log=math.log(ci_low),
        ci_high_log=math.log(ci_high),
        tau2=0.01,
        i2=i2,
        q=10.0,
        q_p=0.2,
    )


def _question():
    return Question(
        id="q",
        text="Q",
        pico=PICO(
            population="adults with T2D",
            intervention="GLP-1 RA",
            comparator="placebo",
            outcome="3-point MACE",
        ),
    )


def _rob(overall):
    return RobAssessment(study_id="S", label="S", domains=[], overall=overall)


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


def test_clean_evidence_is_high_certainty_without_a_key():
    # Low RoB, modest I², a significant CI, and no Claude downgrades -> High.
    g = grade.grade_outcome(
        _question(),
        _pool(0.86, 0.79, 0.94, i2=47.0),
        [_rob(RobJudgment.LOW)] * 8,
        llm_client=None,
    )
    assert g.certainty == GradeRating.HIGH
    assert g.starting_level == GradeRating.HIGH
    assert len(g.domains) == 5
    # The two Claude-judged domains are marked, and default to not-serious with a
    # "not assessed" rationale when there is no key.
    judged = {d.name for d in g.domains if d.by_claude}
    assert judged == {"indirectness", "publication_bias"}


def test_inconsistency_and_imprecision_downgrade_from_computed_values():
    # High heterogeneity -> inconsistency serious; CI crossing 1 -> imprecision serious.
    g = grade.grade_outcome(
        _question(),
        _pool(0.95, 0.80, 1.12, i2=85.0),
        [_rob(RobJudgment.LOW)] * 8,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["inconsistency"].downgrade == -1
    assert by_name["imprecision"].downgrade == -1
    # Two downgrades from High -> Low certainty.
    assert g.certainty == GradeRating.LOW


def test_high_risk_of_bias_downgrades():
    g = grade.grade_outcome(
        _question(),
        _pool(0.86, 0.79, 0.94, i2=20.0),
        [_rob(RobJudgment.HIGH)] + [_rob(RobJudgment.LOW)] * 7,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["risk_of_bias"].serious == "serious"
    assert g.certainty == GradeRating.MODERATE
    # Every downgrade records a rationale.
    assert by_name["risk_of_bias"].rationale


def test_claude_indirectness_downgrade_is_recorded():
    parsed = grade._GradeJudged(
        indirectness="serious",
        indirectness_rationale="Baseline NYHA class differs from the target population.",
        publication_bias="not_serious",
        publication_bias_rationale="Funnel plot symmetric.",
    )
    g = grade.grade_outcome(
        _question(),
        _pool(0.86, 0.79, 0.94, i2=47.0),
        [_rob(RobJudgment.LOW)] * 8,
        llm_client=_StubLLM(parsed),
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["indirectness"].downgrade == -1
    assert "NYHA" in by_name["indirectness"].rationale
    assert g.certainty == GradeRating.MODERATE
    assert g.footnotes  # the downgrade surfaces as a footnote
    assert g.sof_line


def _pool_with_studies(n, *, asymmetric=False):
    """A pool carrying n per-study rows, for the Egger publication-bias path."""
    import math

    from livemeta.core.schema import StudyResult

    studies = []
    for i in range(n):
        vi = 0.01 + 0.05 * i
        yi = (0.10 + 2.5 * vi) if asymmetric else (-0.15 + (0.05 if i % 2 else -0.05))
        studies.append(
            StudyResult(
                study_id=f"S{i}",
                label=f"S{i}",
                yi=yi,
                vi=vi,
                effect=math.exp(yi),
                ci_low=math.exp(yi - 1.96 * math.sqrt(vi)),
                ci_high=math.exp(yi + 1.96 * math.sqrt(vi)),
                weight=100.0 / n,
            )
        )
    pool = _pool(0.86, 0.79, 0.94, i2=30.0)
    return pool.model_copy(update={"k": n, "studies": studies})


def test_pub_bias_deterministic_when_k_ge_10():
    # 10+ studies -> Egger runs; the publication-bias domain becomes deterministic
    # (not Claude-judged) and the Egger result is attached for the funnel plot.
    g = grade.grade_outcome(
        _question(),
        _pool_with_studies(12, asymmetric=False),
        [_rob(RobJudgment.LOW)] * 12,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["publication_bias"].by_claude is False
    assert g.publication_bias_test is not None
    assert g.publication_bias_test.applicable is True


def test_pub_bias_deterministic_flags_asymmetry():
    g = grade.grade_outcome(
        _question(),
        _pool_with_studies(12, asymmetric=True),
        [_rob(RobJudgment.LOW)] * 12,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["publication_bias"].by_claude is False
    assert by_name["publication_bias"].downgrade == -1


def test_pub_bias_falls_back_to_claude_below_10():
    # The 8-study demo pool is below the Egger threshold, so publication bias stays
    # Claude-judged exactly as before — no Egger result.
    g = grade.grade_outcome(
        _question(),
        _pool(0.86, 0.79, 0.94, i2=47.0),
        [_rob(RobJudgment.LOW)] * 8,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["publication_bias"].by_claude is True
    assert g.publication_bias_test is None or g.publication_bias_test.applicable is False


def test_pending_rob_does_not_downgrade_but_is_noted():
    g = grade.grade_outcome(
        _question(),
        _pool(0.86, 0.79, 0.94, i2=47.0),
        [_rob(RobJudgment.PENDING)] * 8,
        llm_client=None,
    )
    by_name = {d.name: d for d in g.domains}
    assert by_name["risk_of_bias"].downgrade == 0
    assert "not" in by_name["risk_of_bias"].rationale.lower()
    assert g.certainty == GradeRating.HIGH
