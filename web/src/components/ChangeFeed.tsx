import { Link } from "react-router-dom";
import type { ChangeType, LandscapeChange, LandscapeDiff } from "../lib/types";
import { Icon } from "./Icon";
import { StagePill } from "./StagePill";

// The market-intelligence change-feed: a living timeline of competitive moves,
// grouped by month, each row a node on a rail. Copy leads with plain language
// (the summary); clinical detail (estimates) is secondary.

const TYPE_STYLE: Record<ChangeType, { tone: string; icon: string; label: string }> = {
  advanced: { tone: "bg-accent-container text-on-accent-container", icon: "arrow_upward", label: "Advanced" },
  new_program: { tone: "bg-accent-container text-on-accent-container", icon: "add", label: "New program" },
  readout: { tone: "bg-risk-low-container text-risk-low", icon: "science", label: "Readout" },
  setback: { tone: "bg-risk-high-container text-risk-high", icon: "cancel", label: "Setback" },
  evidence_moved: { tone: "bg-risk-low-container text-risk-low", icon: "trending_up", label: "Evidence moved" },
  conflict_opened: { tone: "bg-risk-some-container text-risk-some", icon: "warning", label: "Conflict opened" },
};

function monthLabel(date?: string | null): string {
  if (!date) return "Undated";
  const d = new Date(`${date.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function tone(change: LandscapeChange): string {
  // An evidence move that loses significance reads as a setback (red), not a win.
  if (change.change_type === "evidence_moved" && /no longer/i.test(change.summary)) {
    return "bg-risk-high-container text-risk-high";
  }
  return TYPE_STYLE[change.change_type].tone;
}

function groupByMonth(changes: LandscapeChange[]): [string, LandscapeChange[]][] {
  const groups = new Map<string, LandscapeChange[]>();
  for (const c of changes) {
    const key = monthLabel(c.date);
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(c);
  }
  return [...groups.entries()];
}

export function ChangeFeed({ diff }: { diff: LandscapeDiff }) {
  // Pooled-evidence moves are not shown on the market-intelligence surface.
  const changes = diff.changes.filter((c) => c.change_type !== "evidence_moved");

  if (changes.length === 0) {
    return (
      <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
        Nothing moved in <span className="font-medium">{diff.condition}</span> over this window.
      </div>
    );
  }

  return (
    <div className="rounded-md hairline bg-card-light p-5">
      {groupByMonth(changes).map(([month, rows]) => (
        <div key={month} className="mb-2">
          <div className="mb-2 text-label-caps uppercase text-ink-muted-light">{month}</div>
          {rows.map((c, i) => {
            const style = TYPE_STYLE[c.change_type];
            return (
              <div key={`${c.asset_name}-${c.indication}-${i}`} className="flex gap-3 pb-4">
                <div className="flex flex-col items-center">
                  <span className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full bg-accent" />
                  <span className="mt-1 w-px flex-1 bg-hairline-light" />
                </div>
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[11px] font-semibold ${tone(c)}`}
                    >
                      <Icon name={style.icon} size={12} />
                      {style.label}
                    </span>
                    {c.date && <span className="font-mono text-[11px] text-ink-muted-light">{c.date}</span>}
                  </div>
                  <div className="mt-1.5 text-[13px] text-ink-light">
                    <Link
                      to={`/asset/${encodeURIComponent(c.asset_name)}`}
                      className="font-medium hover:underline"
                    >
                      {c.asset_name}
                    </Link>{" "}
                    · {c.indication}
                    {c.change_type === "advanced" && c.from_phase && c.to_phase && (
                      <span className="ml-2 inline-flex items-center gap-1 align-middle">
                        <StagePill phase={c.from_phase} />
                        <Icon name="arrow_forward" size={12} className="text-ink-muted-light" />
                        <StagePill phase={c.to_phase} />
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-[12px] text-ink-muted-light">
                    {c.summary}
                    {c.change_type === "evidence_moved" &&
                      c.estimate_prev != null &&
                      c.estimate_curr != null && (
                        <span className="ml-2 font-mono">
                          {c.estimate_prev.toFixed(2)} → {c.estimate_curr.toFixed(2)}
                        </span>
                      )}
                    {c.provenance.length > 0 && c.provenance[0].source_url && (
                      <a
                        href={c.provenance[0].source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-2 inline-flex items-center gap-1 text-accent hover:underline"
                      >
                        <Icon name="description" size={12} /> source
                      </a>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
