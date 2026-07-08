import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReviews } from "../lib/api";
import { Icon } from "../components/Icon";
import type { ReviewSummary } from "../lib/types";

function statusPill(status: string) {
  const cfg: Record<string, { label: string; dot: string; box: string }> = {
    "conclusion-moved": {
      label: "Conclusion moved",
      dot: "bg-risk-some",
      box: "bg-risk-some-container text-risk-some",
    },
    "estimate-updated": {
      label: "Estimate updated",
      dot: "bg-accent",
      box: "bg-accent-container text-accent",
    },
    unchanged: {
      label: "Unchanged",
      dot: "bg-outline",
      box: "bg-surface-container-high text-ink-muted-light",
    },
  };
  const c = cfg[status] ?? cfg.unchanged;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${c.box}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
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
          <h1 className="font-sans text-display-lg text-ink-light">Reviews Dashboard</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Living meta-analyses that update themselves as new trials land.
          </p>
        </div>
        <Link
          to="/ask"
          className="inline-flex items-center gap-1.5 rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          <Icon name="add" size={18} />
          New Review
        </Link>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load reviews. Is the backend running on :8000?
        </p>
      )}

      {rows && rows.length === 0 && (
        <div className="rounded-md hairline bg-card-light p-8 text-center">
          <p className="text-[14px] text-ink-muted-light">
            No reviews yet.{" "}
            <Link to="/ask" className="text-accent underline">
              Ask a clinical question
            </Link>{" "}
            to run your first one.
          </p>
        </div>
      )}

      {rows && rows.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-md hairline bg-card-light">
            <div className="grid min-w-[680px] grid-cols-12 gap-3 hairline-b bg-surface-container-low p-3 text-label-caps uppercase text-ink-muted-light">
              <div className="col-span-6">Question</div>
              <div className="col-span-1 text-center">Trials</div>
              <div className="col-span-3 text-right">Estimate [95% CI]</div>
              <div className="col-span-2 text-right">Status</div>
            </div>
            {rows.map((row) => (
              <Link
                key={row.question_id}
                to={`/reviews/${row.question_id}/evidence`}
                className="group grid min-w-[680px] grid-cols-12 items-center gap-3 hairline-b p-3 last:border-0 hover:bg-surface-container-low"
              >
                <div className="col-span-6">
                  <p className="truncate text-[14px] text-ink-light group-hover:text-accent">
                    {row.text}
                  </p>
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
          <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
            <Icon name="info" size={16} />
            Each review re-pools and flags a change automatically when a new trial lands.
          </p>
        </>
      )}
    </div>
  );
}
