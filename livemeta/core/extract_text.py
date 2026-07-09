"""The structured-output contract for Claude reading a published trial.

`ExtractedEffect` is what we ask Claude to return after reading an abstract,
full text, and parsed tables: one effect variant (binary 2x2 / continuous
mean-SD-n / ratio+CI) with a source snippet and a self-reported confidence. The
model never computes the pooled numbers — it only reports what the paper says,
with the exact sentence or cell it read it from. Code does every arithmetic step
downstream and flags anything low-confidence rather than inventing precision.
"""

from __future__ import annotations

from pydantic import BaseModel

_SYSTEM_HINT = (
    "You are reading one randomized trial's published report to extract its "
    "primary-outcome effect for a meta-analysis. Return exactly one variant: a "
    "binary 2x2 table (events and totals per arm), continuous statistics (mean "
    "with SD or SE, and n per arm), or a reported ratio with its 95% confidence "
    "interval. Quote the exact sentence or table cell you read it from in "
    "source_snippet. Do NOT compute, convert, or infer numbers not stated in the "
    "text — if the effect is not clearly reported, set found=false. Set "
    "confidence to 'low' whenever the numbers are ambiguous; abstaining is "
    "correct, guessing is not."
)


class ExtractedEffect(BaseModel):
    """One effect read from published text, before any arithmetic in code."""

    found: bool = False
    confidence: str = "low"  # high | moderate | low
    variant: str = "none"  # binary | continuous | ratio_ci | none
    source_snippet: str = ""

    # binary
    events_treatment: int | None = None
    total_treatment: int | None = None
    events_control: int | None = None
    total_control: int | None = None

    # continuous — SD preferred; SE or a mean CI are converted to SD in code
    mean_treatment: float | None = None
    sd_treatment: float | None = None
    se_treatment: float | None = None
    ci_low_treatment: float | None = None
    ci_high_treatment: float | None = None
    n_treatment: int | None = None
    mean_control: float | None = None
    sd_control: float | None = None
    se_control: float | None = None
    ci_low_control: float | None = None
    ci_high_control: float | None = None
    n_control: int | None = None

    # ratio + CI (HR/RR/OR reported directly)
    ratio: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None


def build_prompt(source_doc: dict) -> str:
    """The user message: the paper's title, abstract, full text, and tables."""
    parts = [f"Title: {source_doc.get('title', '')}"]
    if source_doc.get("abstract"):
        parts.append(f"\nAbstract:\n{source_doc['abstract']}")
    if source_doc.get("full_text"):
        parts.append(f"\nFull text:\n{source_doc['full_text'][:12000]}")
    for i, table in enumerate(source_doc.get("tables", []), 1):
        rows = "\n".join(" | ".join(r) for r in table.get("rows", []))
        parts.append(f"\nTable {i} ({table.get('caption', '')}):\n{rows}")
    return "\n".join(parts)


def system_hint() -> str:
    return _SYSTEM_HINT
