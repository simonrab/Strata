"""Claude reads a trial's eligibility into a structured sub-population.

The refinement that turns a flat indication ("Obesity") into the precise target
a trial actually enrolls ("obesity + established CVD, adults >=45"). Mirrors
`extract_text.py`: Claude reports what the eligibility says (with the exact
snippet and a confidence); deterministic code maps it, and **keyless or
low-confidence reads degrade to the base indication alone — never a fabricated
sub-group**. The precedent for reading eligibility is `homogeneity._trial_digest`.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from ..schema import Provenance
from .ctgov_pipeline import _condition, _nct
from .schema import SubPopulation

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_HINT = (
    "You are reading one randomized trial's eligibility criteria to identify the "
    "precise sub-population it enrolls within a broad indication. Return the base "
    "indication and refine it: minimum and maximum age (integer years, if "
    "stated), sex, the key comorbidities the trial REQUIRES (e.g. established "
    "cardiovascular disease, chronic kidney disease, type 2 diabetes — as short "
    "snake_case tokens), and line of therapy / prior treatment if stated. Quote "
    "the exact eligibility sentence you relied on in source_snippet. Do NOT invent "
    "criteria the text does not state; set found=false if eligibility is absent, "
    "and confidence to 'low' whenever it is ambiguous. Abstaining is correct."
)


class _SubPopRead(BaseModel):
    found: bool = False
    confidence: str = "low"  # high | moderate | low
    source_snippet: str = ""
    base_indication: str = ""
    age_min: int | None = None
    age_max: int | None = None
    sex: str | None = None
    comorbidities: list[str] = Field(default_factory=list)
    line_of_therapy: str | None = None
    prior_treatment: str | None = None


def _eligibility(study: dict) -> dict:
    return study.get("protocolSection", {}).get("eligibilityModule", {})


def _base_only(study: dict, snippet: str = "") -> SubPopulation:
    nct = _nct(study)
    return SubPopulation(
        base_indication=_condition(study),
        provenance=[
            Provenance(
                trial_id=nct,
                snippet=snippet or "Base indication only (eligibility not refined).",
                source_url=f"https://clinicaltrials.gov/study/{nct}",
                field="eligibilityModule",
            )
        ],
    )


def _resolve_client(llm_client):
    if llm_client is not None:
        return llm_client
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            return anthropic.Anthropic()
        except Exception:
            return None
    return None


def _prompt(study: dict) -> str:
    elig = _eligibility(study)
    return (
        f"Base indication (from conditions): {_condition(study)}\n"
        f"minimumAge: {elig.get('minimumAge', '')}\n"
        f"maximumAge: {elig.get('maximumAge', '')}\n"
        f"sex: {elig.get('sex', '')}\n"
        f"Eligibility criteria:\n{str(elig.get('eligibilityCriteria', ''))[:6000]}"
    )


def extract_sub_population(study: dict, llm_client=None) -> SubPopulation:
    """Structure a trial's target sub-population; degrade to base indication only."""
    client = _resolve_client(llm_client)
    if client is None or not _eligibility(study).get("eligibilityCriteria"):
        return _base_only(study)

    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        read: _SubPopRead = client.messages.parse(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": _prompt(study)}],
            output_format=_SubPopRead,
        ).parsed_output
    except Exception:
        return _base_only(study)

    if not read.found or read.confidence == "low":
        return _base_only(study)

    nct = _nct(study)
    return SubPopulation(
        base_indication=read.base_indication or _condition(study),
        age_min=read.age_min,
        age_max=read.age_max,
        sex=read.sex,
        comorbidities=[c.strip().lower() for c in read.comorbidities if c.strip()],
        line_of_therapy=read.line_of_therapy,
        prior_treatment=read.prior_treatment,
        provenance=[
            Provenance(
                trial_id=nct,
                snippet=read.source_snippet,
                source_url=f"https://clinicaltrials.gov/study/{nct}",
                field="eligibilityModule.eligibilityCriteria",
            )
        ],
    )
