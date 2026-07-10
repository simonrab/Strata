"""Trial search: turn a PICO into a query and return candidate trials.

Wraps the ClinicalTrials.gov v2 free-text search. The query builder is
deterministic (no LLM); Claude-driven query refinement is a later slice.
"""

from __future__ import annotations

from .schema import PICO, TrialCandidate
from .sources.clinicaltrials import ClinicalTrialsClient


def build_query(pico: PICO) -> str:
    """A CT.gov free-text term from the intervention and outcome only.

    Population *and* comparator are deliberately left out: both over-constrain
    CT.gov's free-text AND-match. The comparator (usually "Placebo") drops every
    active-comparator trial and every record that just doesn't index the word,
    collapsing broad questions to one or two hits. Both fields are still used
    downstream for eligibility and extraction — they just don't narrow the
    candidate search here.
    """
    parts = [p.strip() for p in (pico.intervention, pico.outcome) if p and p.strip()]
    return " AND ".join(parts)


def search_trials(
    pico: PICO,
    max_results: int = 1000,
    client: ClinicalTrialsClient | None = None,
    interventional_only: bool = True,
) -> list[TrialCandidate]:
    """Search CT.gov for candidate trials matching the PICO.

    `interventional_only` (on by default) applies CT.gov's study-type filter at
    the API — the first, cheapest screen — so the candidate set the pipeline
    screens clinically is already limited to interventional trials.
    """
    client = client or ClinicalTrialsClient()
    query = build_query(pico)
    hits = client.search_studies(
        query, page_size=max_results, interventional_only=interventional_only
    )
    return [
        TrialCandidate(nct_id=h.get("nct_id", ""), title=h.get("title", ""))
        for h in hits
        if h.get("nct_id")
    ]
