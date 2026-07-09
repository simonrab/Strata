"""Route a reference id to the evidence source that can serve it.

`NCT…` → ClinicalTrials.gov (structured results); `PMID:…` / `PMC…` → Europe PMC
(published text). This is the pipeline's default fetch, so one review can draw
trials from both sources. Clients are injectable so tests run offline.
"""

from __future__ import annotations

from .base import EvidenceSource
from .clinicaltrials import ClinicalTrialsClient
from .europepmc import EuropePmcClient


class SourceRouter:
    def __init__(
        self,
        ctgov: EvidenceSource | None = None,
        europepmc: EvidenceSource | None = None,
    ):
        self._ctgov = ctgov or ClinicalTrialsClient()
        self._europepmc = europepmc or EuropePmcClient()

    def source_for(self, ref_id: str) -> EvidenceSource:
        rid = ref_id.strip().upper()
        if rid.startswith("NCT"):
            return self._ctgov
        if rid.startswith("PMID:") or rid.startswith("PMC"):
            return self._europepmc
        raise ValueError(f"Unrecognized reference id shape: {ref_id!r}")

    def fetch(self, ref_id: str) -> dict:
        return self.source_for(ref_id).fetch_study(ref_id)
