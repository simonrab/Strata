"""Search -> screen -> include: the eligibility gate that makes this a review.

Between retrieval and extraction, each candidate is screened against the
question's PICO. Two stages, split by the core principle (CLAUDE.md): a
deterministic pre-filter removes what code can judge with certainty (an
explicitly non-interventional / non-randomized design), then Claude reads the
remaining trials and judges include/exclude with a reason and a source quote.
Keyless, the clinical read cannot run, so cleared trials are auto-included and
marked `by_claude=False` — the funnel shows the screen ran in reduced mode
rather than pretending it screened.
"""

from livemeta.core.schema import EligibilityDecision, PICO, Question
from livemeta.core.screen import screen_candidates


def _question() -> Question:
    return Question(
        id="q",
        text="q",
        pico=PICO(
            population="adults with type 2 diabetes",
            intervention="GLP-1 receptor agonist",
            comparator="placebo",
            outcome="MACE",
        ),
    )


def _study(nct: str, study_type: str | None = None, allocation: str | None = None) -> dict:
    design: dict = {}
    if study_type is not None:
        design["studyType"] = study_type
    if allocation is not None:
        design["designInfo"] = {"allocation": allocation}
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": f"Trial {nct}"},
            "designModule": design,
        }
    }


class _StubParsed:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _StubLLM:
    """Returns a fixed screen judgment for every trial (mirrors homogeneity tests)."""

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


# --- Deterministic pre-filter (runs with or without a key) -------------------


def test_observational_study_is_excluded_deterministically():
    studies = {"NCT1": _study("NCT1", study_type="OBSERVATIONAL")}
    decisions = screen_candidates(_question(), studies, llm_client=None)

    assert len(decisions) == 1
    d = decisions[0]
    assert d.decision == "excluded"
    assert d.domain == "design"
    assert d.by_claude is False  # code judged it, not the model
    assert "intervention" in d.reason.lower() or "observational" in d.reason.lower()


def test_non_randomized_interventional_is_excluded_deterministically():
    studies = {
        "NCT1": _study("NCT1", study_type="INTERVENTIONAL", allocation="NON_RANDOMIZED")
    }
    decisions = screen_candidates(_question(), studies, llm_client=None)

    assert decisions[0].decision == "excluded"
    assert decisions[0].domain == "design"


def test_missing_design_metadata_is_not_excluded():
    # Benefit of the doubt: absent studyType must not drop a trial (the demo
    # fixtures carry no designModule, and must stay 8-in-8-out).
    studies = {"NCT1": _study("NCT1")}
    decisions = screen_candidates(_question(), studies, llm_client=None)

    assert decisions[0].decision == "included"


# --- Keyless degradation (honest, never silent) ------------------------------


def test_keyless_auto_includes_with_honest_reason():
    studies = {"NCT1": _study("NCT1", study_type="INTERVENTIONAL", allocation="RANDOMIZED")}
    decisions = screen_candidates(_question(), studies, llm_client=None)

    d = decisions[0]
    assert d.decision == "included"
    assert d.by_claude is False
    assert "unavailable" in d.reason.lower() or "no key" in d.reason.lower()


# --- Claude clinical read ----------------------------------------------------


def test_claude_includes_an_eligible_trial():
    from livemeta.core.screen import _ScreenJudged

    judged = _ScreenJudged(eligible=True, reason="Population and comparator match.")
    studies = {"NCT1": _study("NCT1", study_type="INTERVENTIONAL")}
    decisions = screen_candidates(_question(), studies, llm_client=_StubLLM(judged))

    d = decisions[0]
    assert d.decision == "included"
    assert d.by_claude is True


def test_claude_excludes_wrong_population_with_reason_and_quote():
    from livemeta.core.screen import _ScreenJudged

    judged = _ScreenJudged(
        eligible=False,
        domain="population",
        reason="Enrolled children, not the adult T2D population.",
        quote="Inclusion: ages 6-17 years.",
    )
    studies = {"NCT1": _study("NCT1", study_type="INTERVENTIONAL")}
    decisions = screen_candidates(_question(), studies, llm_client=_StubLLM(judged))

    d = decisions[0]
    assert d.decision == "excluded"
    assert d.domain == "population"
    assert d.by_claude is True
    assert d.quote is not None
    assert "6-17" in d.quote.snippet


def test_deterministic_exclusion_skips_the_model():
    # An observational trial is excluded on design alone; the clinical read is
    # never consulted (so an "eligible" stub cannot rescue it).
    from livemeta.core.screen import _ScreenJudged

    judged = _ScreenJudged(eligible=True)
    studies = {"NCT1": _study("NCT1", study_type="OBSERVATIONAL")}
    decisions = screen_candidates(_question(), studies, llm_client=_StubLLM(judged))

    assert decisions[0].decision == "excluded"
    assert decisions[0].domain == "design"


def test_order_follows_question_trial_ids():
    q = _question().model_copy(update={"trial_ids": ["NCT2", "NCT1"]})
    studies = {"NCT1": _study("NCT1"), "NCT2": _study("NCT2")}
    decisions = screen_candidates(q, studies, llm_client=None)

    assert [d.study_id for d in decisions] == ["NCT2", "NCT1"]


def test_returns_a_decision_per_fetched_study():
    studies = {"NCT1": _study("NCT1"), "NCT2": _study("NCT2")}
    decisions = screen_candidates(_question(), studies, llm_client=None)

    assert {d.study_id for d in decisions} == {"NCT1", "NCT2"}
    assert all(isinstance(d, EligibilityDecision) for d in decisions)


# --- Human overrides win over the automated judgment -------------------------


def test_reviewer_override_replaces_the_automated_decision():
    # A trial the deterministic filter would exclude (observational) is re-admitted
    # by a reviewer override — the human's call wins outright.
    studies = {"NCT1": _study("NCT1", study_type="OBSERVATIONAL")}
    override = EligibilityDecision(
        study_id="NCT1",
        decision="included",
        reason="Reviewer confirms eligible on full read.",
        by_claude=False,
        confirmed=True,
    )
    decisions = screen_candidates(
        _question(), studies, llm_client=None, overrides={"NCT1": override}
    )

    assert decisions[0].decision == "included"
    assert decisions[0].confirmed is True
    assert decisions[0].by_claude is False


def test_reviewer_override_can_exclude_an_otherwise_eligible_trial():
    studies = {"NCT1": _study("NCT1", study_type="INTERVENTIONAL")}
    override = EligibilityDecision(
        study_id="NCT1", decision="excluded", reason="Wrong comparator.", by_claude=False
    )
    decisions = screen_candidates(
        _question(), studies, llm_client=None, overrides={"NCT1": override}
    )
    assert decisions[0].decision == "excluded"
