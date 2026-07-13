"""Dynamic PICO parsing: turn a free-text clinical question into a Question.

Division of labour (see CLAUDE.md): Claude *reads and structures* the question
into PICO — it never computes anything. Every question, including the GLP-1 MACE
demo, goes through the same live parse: nothing is hardcoded or short-circuited.
Any model/parse failure degrades to a best-effort fallback rather than raising,
so the pipeline never dies on a bad parse — but note the demo's PICO then depends
on the model being reachable, since there is no curated substitute. The one
exception is an out-of-credits refusal, which raises `LlmCreditsError` so the
front ends can show the real cause instead of a silently degraded PICO.
"""

from __future__ import annotations

import os

from pydantic import BaseModel

from . import search as search_mod
from .schema import PICO, EffectMeasure, Question

# Haiku 4.5 is the default: every Claude call here is a read-and-structure task
# (parse PICO, read a trial, judge a domain) — none touch the math — so the fast,
# cheap model fits. Override for quality or testing with LIVEMETA_LLM_MODEL.
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

class LlmCreditsError(RuntimeError):
    """The Anthropic API refused the call because the account is out of credits.

    Unlike a transient model failure, degrading to the best-effort parse here
    would hand the user a meaningless PICO with no hint why — so this one case
    surfaces as an error for the front ends to display honestly.
    """


# Substrings the anthropic SDK puts in a billing refusal (HTTP 400,
# invalid_request_error: "Your credit balance is too low to access the
# Anthropic API...").
_CREDIT_ERROR_MARKERS = ("credit balance", "insufficient credit")


def _is_credit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _CREDIT_ERROR_MARKERS)


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
    text: str, llm_client=None, search_client=None, epmc_client=None
) -> Question:
    """Parse a free-text clinical question into a Question (PICO + candidate trials).

    Claude structures the PICO (when a client or ANTHROPIC_API_KEY is available),
    then a multi-source search (ClinicalTrials.gov + Europe PMC, when an
    `epmc_client` is supplied) fills in the candidate ids. Any failure degrades to
    a best-effort parse. The GLP-1 MACE demo question is treated exactly like any
    other — there is no special-case short-circuit.
    """
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
        except Exception as exc:
            if _is_credit_error(exc):
                raise LlmCreditsError(
                    "The Anthropic API account is out of credits, so the "
                    "question could not be parsed."
                ) from exc
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
            candidates = search_mod.search_trials(
                pico, client=search_client, epmc_client=epmc_client
            )
            trial_ids = [c.nct_id for c in candidates]
        except Exception:
            trial_ids = []

    return _build_question(text, parsed, trial_ids)
