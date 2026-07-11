import { memo, useMemo } from "react";
import { Link } from "react-router-dom";
import type { LandscapeCell, Phase } from "../lib/types";
import { Icon } from "./Icon";
import { StagePill } from "./StagePill";

// Development phases in ascending order of advancement. This is the board's
// column axis: fixed, ordered, and dense — every asset sits in exactly one of
// these, so (unlike an asset × indication matrix) there is no blank space.
export const PHASE_ORDER: Phase[] = [
  "preclinical",
  "phase_1",
  "phase_1_2",
  "phase_2",
  "phase_2_3",
  "phase_3",
  "phase_4",
  "filed",
  "approved",
  "withdrawn",
  "unknown",
];

// A broad scope (a company like Novo Nordisk, or a condition like "Obesity") can
// return ~1000 assets. Cap cards PER COLUMN rather than globally: a single global
// cap, ordered by advancement, collapses a big pipeline into just its most-
// advanced column (e.g. all Phase 4) and hides every earlier stage. A per-column
// cap keeps every occupied stage visible and the board responsive.
const COLUMN_CARD_LIMIT = 50;

function AssetCard({
  cell,
  condition,
}: {
  cell: LandscapeCell;
  // When set, the card shows a Timeline chip into the condition-scoped drill-in.
  // Omitted on the company board, whose events live in a sponsor partition the
  // condition timeline route can't read — the drug name → dossier is the drill-in.
  condition?: string;
}) {
  const readOut = cell.latest_event?.event_type === "readout";
  return (
    <div className="rounded-md hairline bg-card-light p-2.5" data-testid="asset-card">
      <div className="flex items-start justify-between gap-1">
        <Link
          to={`/asset/${encodeURIComponent(cell.asset_name)}`}
          className="text-[13px] font-medium leading-tight text-ink-light hover:text-accent hover:underline"
          title={`Full dossier — every trial for ${cell.asset_name} across indications`}
        >
          {cell.asset_name}
        </Link>
        {cell.conflict && (
          <span title={cell.conflict_note ?? "Sources disagree on the current stage"}>
            <Icon name="warning" size={14} className="text-risk-some" label="source conflict" />
          </span>
        )}
      </div>
      <p className="mt-1 truncate text-[11px] text-ink-muted-light" title={cell.indication}>
        {cell.indication}
      </p>
      {cell.sponsor && (
        <Link
          to={`/company/${encodeURIComponent(cell.sponsor)}`}
          className="block truncate text-[10px] text-ink-muted-light hover:text-accent hover:underline"
          title={`See ${cell.sponsor}'s entire pipeline`}
        >
          {cell.sponsor}
        </Link>
      )}
      {readOut && (
        <span className="mt-1 inline-flex items-center gap-0.5 text-[10px] text-risk-low">
          <Icon name="check_circle" size={11} label="has read out" /> Read out
        </span>
      )}
      {condition && (
        <Link
          to={`/landscape/asset/${encodeURIComponent(cell.asset_name)}?condition=${encodeURIComponent(condition)}`}
          className="mt-1 inline-flex items-center gap-0.5 text-[10px] text-accent hover:underline"
        >
          Timeline <Icon name="chevron_right" size={12} />
        </Link>
      )}
    </div>
  );
}

// Groups cells into a Kanban-style board with one column per occupied phase.
// Memoized on cells/condition/indication so typing in a parent search box does
// not re-render the whole board on every keystroke.
export const PipelineBoard = memo(function PipelineBoard({
  cells: allCells,
  asOf,
  indication,
  condition,
}: {
  cells: LandscapeCell[];
  asOf?: string | null;
  indication: string | null;
  // Passed through to each card's Timeline chip; omitted for the company board.
  condition?: string;
}) {
  const { columns, hiddenTotal } = useMemo(() => {
    const cells = (allCells ?? []).filter(
      (c) => indication === null || c.indication === indication
    );

    const byPhase = new Map<Phase, LandscapeCell[]>();
    for (const c of cells) {
      const list = byPhase.get(c.current_phase) ?? [];
      list.push(c);
      byPhase.set(c.current_phase, list);
    }
    // One column per occupied phase, in phase order. Each column is capped
    // independently so no stage can crowd out another; overflow is surfaced as a
    // per-column "+N more" rather than silently dropped.
    let hiddenTotal = 0;
    const columns = PHASE_ORDER.filter((p) => byPhase.has(p)).map((phase) => {
      const all = byPhase.get(phase)!.sort((a, b) => a.asset_name.localeCompare(b.asset_name));
      const hidden = Math.max(0, all.length - COLUMN_CARD_LIMIT);
      hiddenTotal += hidden;
      return { phase, cells: all.slice(0, COLUMN_CARD_LIMIT), total: all.length, hidden };
    });
    return { columns, hiddenTotal };
  }, [allCells, indication]);

  if (columns.length === 0) {
    return (
      <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
        No assets{indication ? ` in ${indication}` : ""}
        {asOf ? ` as of ${asOf}.` : "."}
      </div>
    );
  }

  return (
    <div className="rounded-md hairline bg-surface-container-low p-3">
      {hiddenTotal > 0 && (
        <p className="mb-2 px-1 text-[12px] text-ink-muted-light">
          Showing up to {COLUMN_CARD_LIMIT} programs per stage; {hiddenTotal} more are hidden —
          filter by indication to focus.
        </p>
      )}
      <div className="flex gap-3 overflow-x-auto pb-1" data-testid="pipeline-board">
        {columns.map(({ phase, cells, total, hidden }) => (
          <div
            key={phase}
            data-testid={`phase-col-${phase}`}
            className="flex w-56 shrink-0 flex-col"
          >
            <div className="mb-2 flex items-center justify-between px-1">
              <StagePill phase={phase} />
              <span className="text-[11px] font-medium text-ink-muted-light">{total}</span>
            </div>
            <div className="flex flex-col gap-2">
              {cells.map((cell) => (
                <AssetCard
                  key={`${cell.asset_name}|${cell.indication}`}
                  cell={cell}
                  condition={condition}
                />
              ))}
            </div>
            {hidden > 0 && (
              <p className="mt-2 px-1 text-[11px] text-ink-muted-light">
                +{hidden} more — filter to see
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
});

// A scope can span hundreds of indications, so a chip row would bury the board.
// When there are only a few, chips are quickest; past that, fall back to a
// compact dropdown that keeps the board as the hero.
const CHIP_LIMIT = 8;

export function IndicationFilter({
  indications,
  active,
  onSelect,
}: {
  indications: string[];
  active: string | null;
  onSelect: (ind: string | null) => void;
}) {
  if (indications.length <= 1) return null;

  if (indications.length > CHIP_LIMIT) {
    return (
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-[12px] text-ink-muted-light">Indication:</span>
        <select
          aria-label="Indication"
          value={active ?? ""}
          onChange={(e) => onSelect(e.target.value || null)}
          className="rounded-sm hairline bg-card-light px-3 py-1.5 text-[13px] text-ink-light outline-none"
        >
          <option value="">All indications ({indications.length})</option>
          {indications.map((ind) => (
            <option key={ind} value={ind}>
              {ind}
            </option>
          ))}
        </select>
        {active && (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[12px] text-accent hover:underline"
          >
            Clear
          </button>
        )}
      </div>
    );
  }

  const chip = (label: string, selected: boolean, value: string | null) => (
    <button
      key={label}
      type="button"
      onClick={() => onSelect(value)}
      className={`rounded-full px-3 py-1 text-[12px] ${
        selected
          ? "bg-accent-container text-on-accent-container"
          : "hairline text-ink-muted-light hover:bg-card-light"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[12px] text-ink-muted-light">Indication:</span>
      {chip("All", active === null, null)}
      {indications.map((ind) => chip(ind, active === ind, ind))}
    </div>
  );
}

// Reconstruct the pipeline at a past point in time. The slider yields a year;
// the parent turns it into an as-of date (or null for "Now") and refetches.
export const MIN_YEAR = 2008;
export const MAX_YEAR = new Date().getFullYear();

export function AsOfSlider({
  year,
  onChange,
}: {
  year: number;
  onChange: (year: number) => void;
}) {
  return (
    <div className="mb-6 flex items-center gap-4 rounded-md hairline bg-card-light px-4 py-3">
      <Icon name="history" size={18} className="text-ink-muted-light" />
      <span className="text-label-caps uppercase text-ink-muted-light">As of</span>
      <input
        type="range"
        aria-label="as of year"
        min={MIN_YEAR}
        max={MAX_YEAR}
        value={year}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1 accent-accent"
      />
      <span data-testid="as-of-label" className="w-24 text-right font-mono text-[13px] text-ink-light">
        {year >= MAX_YEAR ? "Now" : `Dec ${year}`}
      </span>
    </div>
  );
}
