import { Link } from "react-router-dom";
import { useReview } from "../lib/review";
import { ReportView } from "../components/ReportView";

// The immediate post-run report, sourced from the live WebSocket result.
export function Report() {
  const { result } = useReview();

  if (!result || !result.pool) {
    return (
      <div className="mx-auto max-w-3xl px-8 py-12">
        <p className="font-mono text-[13px] text-ink-muted-light">
          No result yet.{" "}
          <Link className="text-accent underline" to="/ask">
            Start a review
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-8 py-12">
      <ReportView result={result} />
      <div className="mt-8 flex gap-3">
        <Link
          to={`/reviews/${result.question.id}/evidence`}
          className="rounded-sm hairline px-4 py-2 text-[13px] text-ink-light hover:bg-surface-container-high"
        >
          Evidence ledger
        </Link>
        <Link
          to="/ask"
          className="rounded-sm hairline px-4 py-2 text-[13px] text-ink-light hover:bg-surface-container-high"
        >
          New review
        </Link>
      </div>
    </div>
  );
}
