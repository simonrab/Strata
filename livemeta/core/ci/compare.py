"""Side-by-side asset profile — operational facts compared, efficacy abstained.

Safety-critical. Two assets' pooled estimates come from *separate* meta-analyses
(different trials, comparators, populations, outcomes), so ranking them is a naive
indirect comparison the Cochrane method forbids. This module therefore:

- compares only **operational** attributes (phase, pivotal trial, enrollment,
  geography, next readout), and
- presents each asset's evidence **in its own context**, gated by a deterministic
  `assess_comparability` verdict that is almost always "not directly comparable" —
  so the UI shows a caveat banner, never a shared axis or a "winner".

Abstaining from the efficacy verdict is the trust story, not a limitation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date

from .ctgov_pipeline import HALTED_STATUSES
from .link import plain_evidence
from .schema import (
    AssetComparison,
    AssetDossier,
    AssetEvidenceContext,
    Comparability,
    ComparisonRow,
    Phase,
    TrialDetail,
    phase_rank,
)

_RATIO_MEASURES = {"HR", "RR", "OR"}


def _today() -> str:
    return date.today().isoformat()


def assess_comparability(a: AssetEvidenceContext, b: AssetEvidenceContext) -> Comparability:
    """The gate. Two estimates are directly comparable only when they share an
    outcome measure, a population, AND a common comparator (an anchored indirect
    comparison). Across independent meta-analyses that essentially never holds, so
    the honest default is "not comparable", with the specific reasons surfaced."""
    reasons: list[str] = []

    if a.badge is None or b.badge is None:
        reasons.append("one or both assets have no committed pooled estimate")
    else:
        if a.badge.state != "pooled" or b.badge.state != "pooled":
            reasons.append("one or both estimates are not a committed pool")
        if a.badge.measure != b.badge.measure:
            reasons.append(
                f"different outcome measures ({a.badge.measure} vs {b.badge.measure})"
            )

    if a.population and b.population and a.population != b.population:
        reasons.append("different trial populations")

    # The comparator is the anchor for any valid indirect comparison; we do not
    # establish a common one, so the comparison stays unanchored.
    if not (a.comparator and b.comparator and a.comparator == b.comparator):
        reasons.append("no common comparator established (unanchored indirect comparison)")

    return Comparability(directly_comparable=not reasons, reasons=reasons)


def _primary_indication(dossier: AssetDossier, indication: str | None) -> str:
    if indication:
        return indication
    counts = Counter(t.indication for t in dossier.trials if t.indication)
    return counts.most_common(1)[0][0] if counts else ""


# CT.gov overallStatus values that mean the trial is still active.
_RUNNING_STATUSES = {
    "RECRUITING",
    "ACTIVE_NOT_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "NOT_YET_RECRUITING",
}

_PHASE_SHORT = {
    Phase.PRECLINICAL: "Preclin",
    Phase.PHASE_1: "Ph1",
    Phase.PHASE_1_2: "Ph1/2",
    Phase.PHASE_2: "Ph2",
    Phase.PHASE_2_3: "Ph2/3",
    Phase.PHASE_3: "Ph3",
    Phase.PHASE_4: "Ph4",
    Phase.FILED: "Filed",
    Phase.APPROVED: "Approved",
    Phase.WITHDRAWN: "Withdrawn",
}


def _count_running(trials: Sequence[TrialDetail]) -> int:
    return sum(1 for t in trials if (t.status or "").upper() in _RUNNING_STATUSES)


def _count_completed(trials: Sequence[TrialDetail]) -> int:
    return sum(1 for t in trials if (t.status or "").upper() == "COMPLETED")


def _count_terminated(trials: Sequence[TrialDetail]) -> int:
    return sum(1 for t in trials if (t.status or "").upper() in HALTED_STATUSES)


def _phase_spread(trials: Sequence[TrialDetail]) -> str:
    """A compact per-phase count, e.g. 'Ph2 5 · Ph3 8 · Ph4 12 · NA 40' — so the
    real distribution shows, not a single (misleading) 'most advanced' phase.
    Non-phased studies (observational, expanded access) fall under NA."""
    counts = Counter(t.phase for t in trials)
    known = sorted((p for p in counts if p != Phase.UNKNOWN), key=phase_rank)
    parts = [f"{_PHASE_SHORT[p]} {counts[p]}" for p in known]
    if counts.get(Phase.UNKNOWN):
        parts.append(f"NA {counts[Phase.UNKNOWN]}")
    return " · ".join(parts) or "—"


def _approvals_cell(dossier: AssetDossier) -> str:
    """FDA approval count plus brand names (from openFDA), or '—' when none."""
    apps = dossier.approvals
    if not apps:
        return "—"
    brands = sorted({b for a in apps for b in (a.brand_names or [])})
    label = str(len(apps))
    if brands:
        label += " · " + ", ".join(brands[:3])
    return label


def _next_readout(trials: Sequence[TrialDetail], today: str) -> str | None:
    future = [
        t.primary_completion_date
        for t in trials
        if t.primary_completion_date and not t.has_results and t.primary_completion_date > today
    ]
    return min(future) if future else None


def _count_row(label: str, raw: list[int]) -> ComparisonRow:
    """A count row with a neutral 'more' marker on the leader (a fact, not a verdict)."""
    top = max(raw) if raw else 0
    distinct = len(set(raw)) > 1
    return ComparisonRow(
        label=label,
        values=[str(v) for v in raw],
        more=[bool(distinct and v == top and v > 0) for v in raw],
    )


def compare_assets(
    store,
    assets: list[str],
    indication: str | None = None,
    *,
    search: Callable[[str], list[dict]] | None = None,
    openfda=None,
    llm_client=None,
    as_of: str | None = None,
) -> AssetComparison:
    """Build the side-by-side profile for two or more assets."""
    from .service import _dossier_evidence_resolver, asset_dossier

    today = (as_of or _today())[:10]
    resolve = _dossier_evidence_resolver(store)
    notes: list[str] = []

    dossiers: dict[str, AssetDossier] = {}
    for asset in assets:
        dossiers[asset] = asset_dossier(
            store, asset, search=search, openfda=openfda, llm_client=llm_client
        )

    inds = {a: _primary_indication(d, indication) for a, d in dossiers.items()}

    # Operational rows — counts, phase spread, approvals, geography, timing.
    trials_by_asset = {a: d.trials for a, d in dossiers.items()}
    rows: list[ComparisonRow] = [
        ComparisonRow(label="Indication", values=[inds[a] or "—" for a in assets]),
        _count_row("Trials", [len(trials_by_asset[a]) for a in assets]),
        _count_row("Running", [_count_running(trials_by_asset[a]) for a in assets]),
        _count_row("Completed", [_count_completed(trials_by_asset[a]) for a in assets]),
        # No "more" marker on terminations — more halts is not a neutral "lead".
        ComparisonRow(
            label="Terminated",
            values=[str(_count_terminated(trials_by_asset[a])) for a in assets],
        ),
        ComparisonRow(label="Phases", values=[_phase_spread(trials_by_asset[a]) for a in assets]),
        ComparisonRow(
            label="FDA approvals", values=[_approvals_cell(dossiers[a]) for a in assets]
        ),
        _count_row("Countries", [len(dossiers[a].countries) for a in assets]),
        ComparisonRow(
            label="Next readout",
            values=[(_next_readout(trials_by_asset[a], today) or "—") for a in assets],
        ),
    ]

    # Evidence — each in its own context, never a comparison row.
    evidence: list[AssetEvidenceContext] = []
    for asset in assets:
        ind = inds[asset]
        badge = resolve(asset, ind) if ind else None
        population = next((g.label for g in dossiers[asset].sub_indications), ind)
        evidence.append(
            AssetEvidenceContext(
                asset_name=asset,
                indication=ind,
                population=population,
                comparator=None,  # not extracted — keeps the comparison honestly unanchored
                plain_summary=plain_evidence(badge),
                badge=badge,
            )
        )

    comparability = (
        assess_comparability(evidence[0], evidence[1])
        if len(evidence) >= 2
        else Comparability(directly_comparable=False, reasons=["need at least two assets"])
    )

    return AssetComparison(
        assets=assets,
        indication=indication,
        rows=rows,
        evidence=evidence,
        comparability=comparability,
        notes=notes,
    )
