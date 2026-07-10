import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getLandscape } from "../lib/api";
import type { Landscape, LandscapeCell } from "../lib/types";
import { Icon } from "../components/Icon";
import { StagePill } from "../components/StagePill";
import { EvidenceBadgeView } from "../components/EvidenceBadgeView";

const MIN_YEAR = 2008;
const MAX_YEAR = new Date().getFullYear();

function Cell({ cell, condition }: { cell: LandscapeCell; condition: string }) {
  return (
    <div className="rounded-sm hairline bg-card-light p-2">
      <div className="flex items-start justify-between gap-1">
        <StagePill phase={cell.current_phase} />
        {cell.conflict && (
          <span title={cell.conflict_note ?? "Sources disagree on the current stage"}>
            <Icon name="warning" size={14} className="text-risk-some" label="source conflict" />
          </span>
        )}
      </div>
      {cell.sponsor && (
        <p className="mt-1 truncate text-[10px] text-ink-muted-light" title={cell.sponsor}>
          {cell.sponsor}
        </p>
      )}
      {cell.evidence && <EvidenceBadgeView badge={cell.evidence} />}
      <Link
        to={`/landscape/asset/${encodeURIComponent(cell.asset_name)}?condition=${encodeURIComponent(condition)}`}
        className="mt-1 inline-flex items-center gap-0.5 text-[10px] text-accent hover:underline"
      >
        Timeline <Icon name="chevron_right" size={12} />
      </Link>
    </div>
  );
}

export function CompetitorLandscape() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [year, setYear] = useState(MAX_YEAR);
  const [landscape, setLandscape] = useState<Landscape | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const asOf = year >= MAX_YEAR ? null : `${year}-12-31`;

  useEffect(() => {
    setLoading(true);
    getLandscape(condition, asOf)
      .then((ls) => {
        setLandscape(ls);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, year]);

  const cellByKey = useMemo(() => {
    const map = new Map<string, LandscapeCell>();
    for (const c of landscape?.cells ?? []) map.set(`${c.asset_name}|${c.indication}`, c);
    return map;
  }, [landscape]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">Competitive Landscape</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Which assets are where in development, joined to the living pooled evidence for each.
          </p>
        </div>
      </div>

      <form
        className="mb-5 flex flex-wrap items-center gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setCondition(input.trim() || condition);
        }}
      >
        <div className="flex items-center gap-2 rounded-sm hairline bg-card-light px-3 py-2">
          <Icon name="search" size={16} className="text-ink-muted-light" />
          <input
            aria-label="condition"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="w-64 bg-transparent text-[14px] text-ink-light outline-none"
            placeholder="Condition, e.g. Type 2 Diabetes"
          />
        </div>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Map
        </button>
      </form>

      {/* As-of time slider — reconstruct the pipeline at a past point in time. */}
      <div className="mb-6 flex items-center gap-4 rounded-md hairline bg-card-light px-4 py-3">
        <Icon name="history" size={18} className="text-ink-muted-light" />
        <span className="text-label-caps uppercase text-ink-muted-light">As of</span>
        <input
          type="range"
          aria-label="as of year"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="flex-1 accent-accent"
        />
        <span data-testid="as-of-label" className="w-24 text-right font-mono text-[13px] text-ink-light">
          {year >= MAX_YEAR ? "Now" : `Dec ${year}`}
        </span>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the landscape. Is the backend running on :8000?
        </p>
      )}

      {loading && !landscape && (
        <p className="font-mono text-[13px] text-ink-muted-light">Mapping the landscape…</p>
      )}

      {landscape && landscape.assets.length === 0 && !loading && (
        <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
          No development activity found for <span className="font-medium">{condition}</span>
          {asOf ? ` as of ${asOf}.` : "."}
        </div>
      )}

      {landscape && landscape.assets.length > 0 && (
        <div className="overflow-x-auto rounded-md hairline bg-surface-container-low">
          <table className="min-w-[720px] w-full border-collapse" data-testid="landscape-matrix">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-surface-container-low p-3 text-left text-label-caps uppercase text-ink-muted-light">
                  Asset
                </th>
                {landscape.indications.map((ind) => (
                  <th
                    key={ind}
                    className="p-3 text-left text-label-caps uppercase text-ink-muted-light"
                  >
                    {ind}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {landscape.assets.map((asset) => (
                <tr key={asset} className="hairline-t align-top">
                  <td className="sticky left-0 z-10 bg-surface-container-low p-3 text-[13px] font-medium text-ink-light">
                    {asset}
                  </td>
                  {landscape.indications.map((ind) => {
                    const cell = cellByKey.get(`${asset}|${ind}`);
                    return (
                      <td key={ind} className="p-2">
                        {cell ? (
                          <Cell cell={cell} condition={condition} />
                        ) : (
                          <span className="text-[12px] text-outline-variant">n/a</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Stages come from ClinicalTrials.gov with full provenance; a linked cell carries its
        review's living pooled estimate, GRADE, and homogeneity-gate state.
      </p>
    </div>
  );
}
