import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReviews } from "../lib/api";
import type { ReviewSummary } from "../lib/types";

function statusPill(status: string) {
  const map: Record<string, string> = {
    "conclusion-moved": "bg-[#fef3c7] text-[#b45309] border-[#fde68a]",
    "estimate-updated": "bg-[#dbeafe] text-[#1d4ed8] border-[#bfdbfe]",
    unchanged: "bg-surface-container-high text-ink-muted-light border-hairline-light",
  };
  const label: Record<string, string> = {
    "conclusion-moved": "Conclusion moved",
    "estimate-updated": "Estimate updated",
    unchanged: "Unchanged",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        map[status] ?? map.unchanged
      }`}
    >
      {label[status] ?? "Unchanged"}
    </span>
  );
}

function estimate(row: ReviewSummary): string {
  if (row.estimate == null || row.ci_low == null || row.ci_high == null) return "—";
  return `${row.estimate.toFixed(2)} [${row.ci_low.toFixed(2)}, ${row.ci_high.toFixed(2)}]`;
}

export function Dashboard() {
  const [rows, setRows] = useState<ReviewSummary[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    listReviews()
      .then(setRows)
      .catch(() => setError(true));
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-[32px] font-semibold tracking-tight text-ink-light">
            Reviews Dashboard
          </h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Living meta-analyses that update themselves as new trials land.
          </p>
        </div>
        <Link
          to="/ask"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          + New Review
        </Link>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load reviews. Is the backend running on :8000?
        </p>
      )}

      {rows && rows.length === 0 && (
        <div className="rounded-md border border-hairline-light bg-card-light p-8 text-center">
          <p className="text-[14px] text-ink-muted-light">
            No reviews yet.{" "}
            <Link to="/ask" className="text-secondary underline">
              Ask a clinical question
            </Link>{" "}
            to run your first one.
          </p>
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-hairline-light bg-card-light">
          <div className="grid min-w-[680px] grid-cols-12 gap-3 border-b border-hairline-light bg-surface-container-low p-3 text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
            <div className="col-span-6">Question</div>
            <div className="col-span-1 text-center">Trials</div>
            <div className="col-span-3 text-right">Estimate [95% CI]</div>
            <div className="col-span-2 text-right">Status</div>
          </div>
          {rows.map((row) => (
            <Link
              key={row.question_id}
              to={`/reviews/${row.question_id}/evidence`}
              className="grid min-w-[680px] grid-cols-12 items-center gap-3 border-b border-hairline-light p-3 last:border-0 hover:bg-surface-container-low"
            >
              <div className="col-span-6">
                <p className="truncate text-[14px] text-ink-light">{row.text}</p>
                <p className="mt-0.5 font-mono text-[11px] text-ink-muted-light">
                  {row.question_id} · v{row.versions}
                </p>
              </div>
              <div className="col-span-1 text-center font-mono text-[13px] text-ink-light">
                {row.k}
              </div>
              <div className="col-span-3 text-right font-mono text-[13px] text-ink-light">
                {row.measure} {estimate(row)}
              </div>
              <div className="col-span-2 flex justify-end">{statusPill(row.status)}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
