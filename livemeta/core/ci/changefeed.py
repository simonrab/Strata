"""The market-intelligence change-feed: "what moved" between two dates.

The competitive analogue of the meta-analysis living layer (`core.diff`). It
reconstructs the landscape at two as-of dates — a pure filter over the same dated
`DevelopmentEvent` store, so no new persistence — and reports the deltas:

- a program appeared, a stage advanced, a trial read out, or sources newly
  conflicted (all derivable from the two cell snapshots), and
- the living pooled evidence *moved* — read from each linked review's own version
  history, and reported by whether the **conclusion** changed, never a bare number.

Everything traces to the events (or review versions) that produced it.
"""

from __future__ import annotations

from collections.abc import Callable

from .schema import (
    ChangeType,
    DevelopmentEvent,
    EventType,
    Landscape,
    LandscapeCell,
    LandscapeChange,
    LandscapeDiff,
    Phase,
    phase_rank,
)

# A move smaller than this (relative to the prior estimate) is engine noise, not
# a real evidence shift — mirrors core.diff._REL_EPSILON.
_REL_EPSILON = 0.005

_RATIO_MEASURES = {"HR", "RR", "OR"}
_READOUT_EVENTS = {EventType.READOUT, EventType.APPROVAL}


def _significant(measure: str, ci_low: float | None, ci_high: float | None) -> bool | None:
    """Whether a confidence interval excludes the null (measure-aware)."""
    if ci_low is None or ci_high is None:
        return None
    null = 1.0 if measure in _RATIO_MEASURES else 0.0
    return ci_high < null or ci_low > null


def _key(cell: LandscapeCell) -> tuple[str, str]:
    return (cell.asset_name, cell.indication)


def diff_landscapes(
    prev: Landscape,
    curr: Landscape,
    *,
    since: str | None = None,
    until: str | None = None,
) -> list[LandscapeChange]:
    """The cell-derivable moves between a `since` and an `until` snapshot.

    Pure: two assembled `Landscape`s in, a list of `LandscapeChange` out. Detects
    new programs, stage advances, in-window readouts, and newly-opened conflicts.
    Evidence moves are added separately (they come from review history, not cells).
    """
    prev_by_key = {_key(c): c for c in prev.cells}
    changes: list[LandscapeChange] = []

    for cell in curr.cells:
        key = _key(cell)
        before = prev_by_key.get(key)

        if before is None:
            changes.append(
                LandscapeChange(
                    asset_name=cell.asset_name,
                    indication=cell.indication,
                    change_type=ChangeType.NEW_PROGRAM,
                    date=cell.latest_event.date if cell.latest_event else None,
                    to_phase=cell.current_phase,
                    summary=f"Entered {cell.indication} at {_phase_label(cell.current_phase)}",
                    provenance=list(cell.provenance),
                )
            )
        elif phase_rank(cell.current_phase) > phase_rank(before.current_phase):
            changes.append(
                LandscapeChange(
                    asset_name=cell.asset_name,
                    indication=cell.indication,
                    change_type=ChangeType.ADVANCED,
                    date=cell.latest_event.date if cell.latest_event else None,
                    from_phase=before.current_phase,
                    to_phase=cell.current_phase,
                    summary=(
                        f"Advanced {_phase_label(before.current_phase)} → "
                        f"{_phase_label(cell.current_phase)}"
                    ),
                    provenance=list(cell.provenance),
                )
            )

        # A readout that landed inside the window (the latest visible event is a
        # readout/approval dated after `since`).
        ev = cell.latest_event
        if (
            ev is not None
            and ev.event_type in _READOUT_EVENTS
            and ev.date is not None
            and (since is None or ev.date > since)
        ):
            changes.append(
                LandscapeChange(
                    asset_name=cell.asset_name,
                    indication=cell.indication,
                    change_type=ChangeType.READOUT,
                    date=ev.date,
                    to_phase=cell.current_phase,
                    summary=f"{_readout_word(ev.event_type)} in {cell.indication}",
                    provenance=list(ev.provenance),
                )
            )

        if cell.conflict and not (before and before.conflict):
            changes.append(
                LandscapeChange(
                    asset_name=cell.asset_name,
                    indication=cell.indication,
                    change_type=ChangeType.CONFLICT_OPENED,
                    date=cell.latest_event.date if cell.latest_event else None,
                    summary=cell.conflict_note or "Sources disagree on stage",
                    provenance=list(cell.provenance),
                )
            )

    return changes


def _setback_changes(
    events: list[DevelopmentEvent], since: str | None, until: str | None
) -> list[LandscapeChange]:
    """Halts (terminated/withdrawn/suspended) that landed in the window.

    Scanned from the stored events rather than the cell's single `latest_event`,
    which can hide a setback behind a later trial start for the same asset."""
    out: list[LandscapeChange] = []
    for e in events:
        if e.event_type != EventType.SETBACK or e.date is None:
            continue
        if since is not None and e.date <= since:
            continue
        if until is not None and e.date > until:
            continue
        summary = e.provenance[0].snippet if e.provenance else "Trial halted"
        out.append(
            LandscapeChange(
                asset_name=e.asset_name,
                indication=e.indication,
                change_type=ChangeType.SETBACK,
                date=e.date,
                summary=summary,
                provenance=list(e.provenance),
            )
        )
    return out


def _evidence_change(
    asset: str,
    indication: str,
    snaps: list,  # list[SnapshotMeta]
    since: str | None,
    until: str | None,
) -> LandscapeChange | None:
    """Whether a linked review's *conclusion* moved inside the window.

    Reads the review's own version timeline (headline numbers only). A change is
    reported when significance flips or the estimate shifts beyond noise between
    the last version at/before `since` and the last version at/before `until`.
    """
    dated = [s for s in snaps if s.created_at]
    if not dated:
        return None

    in_window = [
        s
        for s in dated
        if (since is None or s.created_at > since) and (until is None or s.created_at <= until)
    ]
    if not in_window:
        return None  # no new version landed in the window

    current = in_window[-1]
    baseline = None
    if since is not None:
        earlier = [s for s in dated if s.created_at <= since]
        baseline = earlier[-1] if earlier else None

    curr_sig = _significant(current.measure, current.ci_low, current.ci_high)

    if baseline is None:
        summary = "First evidence landed" if curr_sig else "First evidence landed (not yet significant)"
    else:
        prev_sig = _significant(baseline.measure, baseline.ci_low, baseline.ci_high)
        if prev_sig != curr_sig:
            summary = "Benefit now proven" if curr_sig else "Benefit no longer significant"
        elif (
            baseline.estimate
            and current.estimate is not None
            and abs(current.estimate - baseline.estimate) / abs(baseline.estimate) >= _REL_EPSILON
        ):
            summary = "Estimate updated"
        else:
            return None  # a re-run with no material change

    return LandscapeChange(
        asset_name=asset,
        indication=indication,
        change_type=ChangeType.EVIDENCE_MOVED,
        date=(current.created_at or "")[:10] or None,
        estimate_prev=baseline.estimate if baseline else None,
        estimate_curr=current.estimate,
        summary=summary,
    )


def landscape_changes(
    store,
    condition: str,
    since: str | None,
    until: str | None = None,
    search_pipeline: Callable[[str], list[dict]] | None = None,
) -> LandscapeDiff:
    """Assemble "what moved" for a condition between `since` and `until`.

    Reuses `service.get_landscape` to reconstruct the two dated snapshots (seeding
    CT.gov events on first access), diffs the cells, then layers on evidence moves
    from each linked review's version history. Newest change first.
    """
    from .service import get_landscape, slugify

    prev = get_landscape(store, condition, as_of=since, search_pipeline=search_pipeline)
    curr = get_landscape(store, condition, as_of=until)

    # Competitive (cell-derivable) moves — advances, new programs, readouts,
    # conflicts. Pooled-evidence moves are not surfaced on the market layer (that
    # belongs to the review pages); `_evidence_change` remains for callers that want it.
    changes = diff_landscapes(prev, curr, since=since, until=until)

    # Setbacks (halts) are scanned from the stored events, so a termination isn't
    # hidden behind a later trial start on the same cell.
    changes.extend(_setback_changes(store.load_events(slugify(condition)), since, until))

    changes.sort(key=lambda c: (c.date or "", c.asset_name), reverse=True)

    return LandscapeDiff(
        condition=condition,
        since=since,
        until=until,
        changes=changes,
        notes=list(curr.notes),
    )


def _phase_label(phase: Phase) -> str:
    return phase.value.replace("_", " ").title().replace("Phase ", "Phase ")


def _readout_word(event_type: EventType) -> str:
    return "Regulatory approval" if event_type == EventType.APPROVAL else "Trial read out"
