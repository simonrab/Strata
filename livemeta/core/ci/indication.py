"""Cluster an indication's trials into a sub-population taxonomy.

Bottom-up and deterministic: trials with the same `SubPopulation.signature()`
form one node (e.g. "obesity + established CVD, adults >=45"). No fuzzy ML — the
taxonomy is whatever the trials' eligibility says it is. When sub-populations are
unread, trials fall back to the base indication (one node), which is honest to
the fact that we haven't refined them yet.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence

from .dossier import EvidenceResolver, _country_counts
from .schema import (
    EvidenceBadge,
    IndicationMap,
    IndicationNode,
    Source,
    SourceSelection,
    TrialDetail,
)


def _node_key(t: TrialDetail) -> tuple[str, str]:
    if t.sub_population is not None:
        return t.sub_population.signature(), t.sub_population.display()
    ind = t.indication or "Unspecified"
    return ind.lower(), ind


def build_indication_map(
    indication: str,
    trials: Sequence[TrialDetail],
    *,
    selection: SourceSelection | None = None,
    evidence_for: EvidenceResolver | None = None,
) -> IndicationMap:
    selection = selection or SourceSelection.default()
    trials = list(trials) if selection.allows(Source.CTGOV) else []

    buckets: dict[str, list[TrialDetail]] = {}
    labels: dict[str, str] = {}
    subpops: dict[str, object] = {}
    for t in trials:
        sig, label = _node_key(t)
        buckets.setdefault(sig, []).append(t)
        labels.setdefault(sig, label)
        if sig not in subpops:
            subpops[sig] = t.sub_population

    nodes: list[IndicationNode] = []
    for sig, ts in buckets.items():
        stage_dist = Counter(t.phase.value for t in ts)
        badge = evidence_for("", labels[sig]) if evidence_for else None
        nodes.append(
            IndicationNode(
                signature=sig,
                label=labels[sig],
                sub_population=subpops[sig],
                assets=sorted({t.asset_name for t in ts if t.asset_name}),
                trial_count=len(ts),
                stage_distribution=dict(stage_dist),
                countries=_country_counts(ts),
                evidence=badge,
            )
        )
    nodes.sort(key=lambda n: (-n.trial_count, n.label))
    return IndicationMap(
        indication=indication, sources=list(selection.enabled), nodes=nodes
    )
