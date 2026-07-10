import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReviews } from "../lib/api";
import { Icon } from "../components/Icon";
import type { ReviewSummary } from "../lib/types";

// Living-status chip: a hairline in the semantic colour plus a solid dot. No
// filled background — stability is stated quietly, change earns the colour.
function statusPill(status: string) {
  const cfg: Record<string, { label: string; dot: string; tone: string }> = {
    "conclusion-moved": {
      label: "Conclusion moved",
      dot: "bg-risk-some",
      tone: "border-risk-some text-risk-some",
    },
    "estimate-updated": {
      label: "Estimate updated",
      dot: "bg-accent",
      tone: "border-accent text-accent",
    },
    unchanged: {
      label: "Unchanged",
      dot: "bg-outline",
      tone: "border-outline-variant text-ink-muted-light",
    },
  };
  const c = cfg[status] ?? cfg.unchanged;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border bg-card-light px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${c.tone}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

function answerText(row: ReviewSummary): string {
  if (row.estimate == null || row.ci_low == null || row.ci_high == null) return "Not pooled";
  return `${row.measure} ${row.estimate.toFixed(2)} [${row.ci_low.toFixed(2)}, ${row.ci_high.toFixed(2)}]`;
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
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">Reviews</h1>
          <p className="mt-1 text-[15px] text-ink-muted-light">
            Living meta-analyses. Each re-pools itself when a new trial reads out.
          </p>
        </div>
        <Link
          to="/ask"
          className="inline-flex items-center gap-1.5 rounded-md bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          <Icon name="add" size={18} />
          New review
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
          <div className="flex flex-col gap-2.5">
            {rows.map((row) => {
              const pooled = row.estimate != null;
              return (
                <Link
                  key={row.question_id}
                  to={`/reviews/${row.question_id}/evidence`}
                  className="group grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-1.5 rounded-md hairline bg-card-light p-5 transition-colors hover:border-accent"
                >
                  <p className="col-start-1 text-[15px] font-semibold leading-snug text-ink-light group-hover:text-accent">
                    {row.text}
                  </p>
                  <div className="col-start-2 row-span-2 row-start-1 flex flex-col items-end gap-2 text-right">
                    <span
                      className={`font-mono text-[15px] ${pooled ? "text-ink-light" : "text-ink-muted-light"}`}
                    >
                      {answerText(row)}
                    </span>
                    {statusPill(row.status)}
                  </div>
                  <p className="col-start-1 font-mono text-[11px] text-ink-muted-light">
                    {row.k} trials · {row.question_id} · v{row.versions}
                  </p>
                </Link>
              );
            })}
          </div>
          <p className="mt-5 flex items-center gap-2 text-[12px] text-ink-muted-light">
            <Icon name="info" size={16} />
            Each review re-pools and flags a change automatically when a new trial lands.
          </p>
        </>
      )}
    </div>
  );
}
