"""The evidence-source contract shared by every data source.

Both ClinicalTrials.gov (structured results) and Europe PMC (published text)
satisfy this, so the pipeline can fetch a trial without caring where it came
from. `fetch_study` returns whatever that source natively provides — a
structured CT.gov record, or a normalized Europe PMC document — and the extract
dispatcher reads the shape to decide how to structure it.
"""

from __future__ import annotations

from typing import Protocol


class EvidenceSource(Protocol):
    def fetch_study(self, ref_id: str) -> dict: ...

    def search_studies(self, query: str) -> list[dict]: ...
