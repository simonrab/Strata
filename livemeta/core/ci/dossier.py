"""Aggregate an asset's trials + events into an Asset Dossier.

Pure aggregation over already-parsed `TrialDetail`s and `DevelopmentEvent`s (the
service does the CT.gov fetch), so it is fully testable offline. Respects the
`SourceSelection`: free-text events are dropped when their source is off, and
openFDA approvals only appear when `OPENFDA` is enabled.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence

from .schema import (
    Asset,
    AssetDossier,
    CountryCount,
    DevelopmentEvent,
    EvidenceBadge,
    RegulatoryApproval,
    Source,
    SourceSelection,
    SubIndicationGroup,
    TrialDetail,
)

EvidenceResolver = Callable[[str, str], EvidenceBadge | None]  # (asset, indication) -> badge


def _country_counts(trials: Sequence[TrialDetail]) -> list[CountryCount]:
    counter: Counter[str] = Counter()
    for t in trials:
        for c in t.countries:
            counter[c] += 1
    return [
        CountryCount(country=c, trials=n)
        for c, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _subpop_key(t: TrialDetail) -> tuple[str, str, str]:
    """(signature, label, indication) — falls back to the base indication."""
    if t.sub_population is not None:
        return t.sub_population.signature(), t.sub_population.display(), t.sub_population.base_indication
    ind = t.indication or "Unspecified"
    return ind.lower(), ind, ind


def _group_sub_indications(
    asset: str, trials: Sequence[TrialDetail], evidence_for: EvidenceResolver | None
) -> list[SubIndicationGroup]:
    buckets: dict[str, list[TrialDetail]] = {}
    labels: dict[str, tuple[str, str]] = {}
    for t in trials:
        sig, label, indication = _subpop_key(t)
        buckets.setdefault(sig, []).append(t)
        labels.setdefault(sig, (label, indication))
    groups = []
    for sig, ts in buckets.items():
        label, indication = labels[sig]
        badge = evidence_for(asset, indication) if evidence_for else None
        groups.append(
            SubIndicationGroup(
                signature=sig,
                label=label,
                trial_ids=[t.nct_id for t in ts],
                phases=sorted({t.phase.value for t in ts}),
                evidence=badge,
            )
        )
    groups.sort(key=lambda g: (-len(g.trial_ids), g.label))
    return groups


def build_asset_dossier(
    asset_name: str,
    trials: Sequence[TrialDetail],
    events: Sequence[DevelopmentEvent],
    *,
    selection: SourceSelection | None = None,
    approvals: Sequence[RegulatoryApproval] | None = None,
    evidence_for: EvidenceResolver | None = None,
) -> AssetDossier:
    selection = selection or SourceSelection.default()

    # CT.gov trials are the authoritative core; only present when CTGOV is on.
    trials = list(trials) if selection.allows(Source.CTGOV) else []
    events = [e for e in events if selection.allows(e.source_type)]
    approvals = list(approvals) if (approvals and selection.allows(Source.OPENFDA)) else []

    sponsor = next((t.sponsor for t in trials if t.sponsor), None)
    sponsor_class = next((t.sponsor_class for t in trials if t.sponsor_class), None)
    asset = Asset(name=asset_name, sponsor=sponsor, sponsor_class=sponsor_class)

    readouts = [t for t in trials if t.has_results]
    return AssetDossier(
        asset=asset,
        sources=list(selection.enabled),
        trials=list(trials),
        countries=_country_counts(trials),
        events=events,
        readouts=readouts,
        approvals=approvals,
        sub_indications=_group_sub_indications(asset_name, trials, evidence_for),
    )
