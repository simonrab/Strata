import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview } from "../lib/api";
import { ReportView } from "../components/ReportView";
import type { ReviewResult } from "../lib/types";

// The report for a saved review, fetched by id — reflects the latest snapshot,
// including any human confirm/flag re-pool.
export function ReviewReport() {
  const { id = "" } = useParams();
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getReview(id)
      .then(setResult)
      .catch(() => setError(true));
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">No such review.</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading report…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <Link
        to={`/reviews/${id}/evidence`}
        className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light hover:text-secondary"
      >
        ← Evidence ledger
      </Link>
      <div className="mt-4">
        <ReportView result={result} />
      </div>
    </div>
  );
}
