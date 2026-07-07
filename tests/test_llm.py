"""Dynamic PICO parsing: free text -> Question.

Claude structures the clinical question into PICO; a deterministic, keyless
fallback keeps the locked demo running with no ANTHROPIC_API_KEY. These tests
run fully offline with stub clients — the network and the model are never hit.
"""

from livemeta.core import demo, llm
from livemeta.core.schema import PICO, TrialCandidate


class _StubParsed:
    """Mimics the object anthropic's messages.parse() returns."""

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


class _StubSearch:
    def __init__(self, candidates):
        self._candidates = candidates

    def search_studies(self, query, page_size=20):
        return [{"nct_id": c.nct_id, "title": c.title} for c in self._candidates]


def test_locked_demo_question_returns_demo_without_a_key():
    q = llm.parse_question(demo.GLP1_MACE_QUESTION.text)
    assert q.id == "glp1-mace"
    assert len(q.trial_ids) == 8


def test_llm_parses_novel_question_and_searches_for_trials():
    parsed = llm.ParsedPICO(
        population="Adults with hypertension",
        intervention="ACE inhibitor",
        comparator="Placebo",
        outcome="Stroke",
        measure="RR",
    )
    search = _StubSearch([TrialCandidate(nct_id="NCT99999999", title="A trial")])

    q = llm.parse_question(
        "Do ACE inhibitors reduce stroke in adults with hypertension?",
        llm_client=_StubLLM(parsed=parsed),
        search_client=search,
    )

    assert q.pico == PICO(
        population="Adults with hypertension",
        intervention="ACE inhibitor",
        comparator="Placebo",
        outcome="Stroke",
    )
    assert q.measure.value == "RR"
    assert q.trial_ids == ["NCT99999999"]


def test_llm_failure_degrades_to_best_effort_without_raising():
    q = llm.parse_question(
        "Some entirely novel clinical question about drug X and outcome Y.",
        llm_client=_StubLLM(raises=True),
        search_client=_StubSearch([]),
    )
    # Degrades rather than raising; still a usable Question with a PICO.
    assert q.pico.outcome
    assert q.trial_ids == []
