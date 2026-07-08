import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getHistory } from "../lib/api";
import type { SnapshotMeta } from "../lib/types";

function statusFor(meta: SnapshotMeta, latest: number): string {
  if (meta.version === latest) return "Current";
  if (meta.version === 1) return "Initial";
  return "Archived";
}

function estimate(m: SnapshotMeta): string {
  if (m.estimate == null || m.ci_low == null || m.ci_high == null) return "—";
  return `${m.measure} ${m.estimate.toFixed(2)} [${m.ci_low.toFixed(2)}, ${m.ci_high.toFixed(2)}]`;
}

export function AuditTrail() {
  const { id = "" } = useParams();
  const [history, setHistory] = useState<SnapshotMeta[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getHistory(id)
      .then(setHistory)
      .catch(() => setError(true));
  }, [id]);

  const latest = history && history.length ? history[history.length - 1].version : 0;
  const rows = history ? [...history].reverse() : []; // newest first

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-8 py-10">
      <div className="border-b border-hairline-light pb-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-outline">
          History
        </p>
        <h1 className="mt-1 font-sans text-[32px] font-semibold tracking-tight text-ink-light">
          Audit Trail
        </h1>
        <p className="mt-1 text-[14px] text-ink-muted-light">
          Chronological run history and snapshots. Each version is immutable.
        </p>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">Could not load history.</p>
      )}

      {history && history.length === 0 && (
        <p className="rounded-md border border-hairline-light bg-surface-container-low px-4 py-3 text-[13px] text-ink-muted-light">
          No runs yet for this review.
        </p>
      )}

      {rows.length > 0 && (
        <div className="overflow-hidden rounded-md border border-hairline-light bg-card-light">
          <div className="grid grid-cols-12 gap-3 border-b border-hairline-light bg-surface-container-low p-3 text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
            <div className="col-span-3">Date</div>
            <div className="col-span-6">Run snapshot</div>
            <div className="col-span-3 text-right">Status</div>
          </div>
          {rows.map((m) => {
            const status = statusFor(m, latest);
            return (
              <Link
                key={m.version}
                to={`/reviews/${id}/versions/${m.version}`}
                className="grid grid-cols-12 items-center gap-3 border-b border-hairline-light p-3 last:border-0 hover:bg-surface-container-low"
              >
                <div className="col-span-3 font-mono text-[12px] text-ink-muted-light">
                  {m.created_at.slice(0, 10)}
                </div>
                <div className="col-span-6">
                  <p className="font-mono text-[13px] text-ink-light">
                    Run {m.version} · v{m.version}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-ink-muted-light">
                    {m.k} trials · {estimate(m)}
                  </p>
                </div>
                <div className="col-span-3 flex items-center justify-end gap-2">
                  {status === "Current" && (
                    <span className="h-2 w-2 rounded-full bg-[#10b981]" />
                  )}
                  <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted-light">
                    {status}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      <div className="rounded-md border border-hairline-light bg-surface-container-low p-6">
        <h2 className="mb-2 text-[13px] font-medium text-ink-light">
          Snapshot architecture notes
        </h2>
        <p className="max-w-[60ch] font-serif text-[15px] leading-6 text-ink-muted-light">
          Each run snapshot is immutable. Selecting a previous run loads a read-only
          view, preserving the exact evidence, bias assessments, and GRADE certainty
          that were active when it was computed.
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="rounded-sm border border-hairline-light bg-card-light p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-outline">
              Store
            </p>
            <p className="mt-1 font-mono text-[12px] text-ink-light">SQLite · livemeta.db</p>
          </div>
          <div className="rounded-sm border border-hairline-light bg-card-light p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-outline">
              Snapshot key
            </p>
            <p className="mt-1 font-mono text-[12px] text-ink-light">
              {id} · v{latest || "—"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
