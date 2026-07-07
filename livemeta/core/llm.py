"""Dynamic PICO parsing: turn a free-text clinical question into a Question.

Division of labour (see CLAUDE.md): Claude *reads and structures* the question
into PICO — it never computes anything. A deterministic, keyless fallback keeps
the locked demo runnable with no ANTHROPIC_API_KEY, and any model/parse failure
degrades to that fallback rather than raising, so the pipeline never dies on a
bad parse.
"""

from __future__ import annotations

import os

from pydantic import BaseModel

from . import demo, search as search_mod
from .schema import PICO, EffectMeasure, Question

# Opus 4.8 is the default per the Anthropic API guidance; override for testing or
# cost with LIVEMETA_LLM_MODEL.
_DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM_HINT = (
    "You structure a clinician's question into PICO for a meta-analysis. "
    "Extract the population, intervention, comparator, and single primary outcome, "
    "plus the most appropriate effect measure (HR for time-to-event, RR or OR for "
    "binary outcomes). Do not infer trials or numbers — only structure the question."
)


class ParsedPICO(BaseModel):
    """The structured output we ask Claude to return."""

    population: str
    intervention: str
    comparator: str
    outcome: str
    measure: str = "HR"


def _matches_demo(text: str) -> bool:
    """The locked GLP-1 MACE demo question — recognized so the memorable demo is
    deterministic and never needs a key or the model."""
    low = text.lower()
    return ("glp-1" in low or "glp1" in low) and (
        "mace" in low or "cardiovascular" in low
    )


def _measure(value: str) -> EffectMeasure:
    try:
        return EffectMeasure(value.upper())
    except ValueError:
        return EffectMeasure.HR


def _build_question(text: str, parsed: ParsedPICO, trial_ids: list[str]) -> Question:
    qid = "q-" + "".join(c if c.isalnum() else "-" for c in text.lower())[:40].strip("-")
    return Question(
        id=qid,
        text=text,
        pico=PICO(
            population=parsed.population,
            intervention=parsed.intervention,
            comparator=parsed.comparator,
            outcome=parsed.outcome,
        ),
        measure=_measure(parsed.measure),
        trial_ids=trial_ids,
    )


def _fallback_parse(text: str) -> ParsedPICO:
    """Best-effort, no-model structuring — low confidence, but never raises."""
    return ParsedPICO(
        population="Unspecified population",
        intervention="Unspecified intervention",
        comparator="Placebo or standard care",
        outcome=text.strip(),
        measure="HR",
    )


def _llm_parse(text: str, client) -> ParsedPICO:
    model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
    response = client.messages.parse(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_HINT,
        messages=[{"role": "user", "content": text}],
        output_format=ParsedPICO,
    )
    return response.parsed_output


def parse_question(
    text: str, llm_client=None, search_client=None
) -> Question:
    """Parse a free-text clinical question into a Question (PICO + candidate trials).

    The locked demo short-circuits to the recorded question so the live demo is
    deterministic and keyless. Otherwise Claude structures the PICO (when a client
    or ANTHROPIC_API_KEY is available), then ClinicalTrials.gov search fills in the
    candidate trial ids. Any failure degrades to a best-effort parse.
    """
    if _matches_demo(text):
        return demo.GLP1_MACE_QUESTION.model_copy(update={"text": text})

    client = llm_client
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            client = anthropic.Anthropic()
        except Exception:
            client = None

    parsed: ParsedPICO
    if client is not None:
        try:
            parsed = _llm_parse(text, client)
        except Exception:
            parsed = _fallback_parse(text)
    else:
        parsed = _fallback_parse(text)

    pico = PICO(
        population=parsed.population,
        intervention=parsed.intervention,
        comparator=parsed.comparator,
        outcome=parsed.outcome,
    )

    trial_ids: list[str] = []
    if search_client is not None:
        try:
            candidates = search_mod.search_trials(pico, client=search_client)
            trial_ids = [c.nct_id for c in candidates]
        except Exception:
            trial_ids = []

    return _build_question(text, parsed, trial_ids)
