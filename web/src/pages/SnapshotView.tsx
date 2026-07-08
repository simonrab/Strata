import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getVersion } from "../lib/api";
import { ReportView } from "../components/ReportView";
import type { ReviewResult } from "../lib/types";

// A read-only view of one historical snapshot, reached from the audit trail.
// Reuses the standard report so a past run looks exactly as it did when computed.
export function SnapshotView() {
  const { id = "", version = "" } = useParams();
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getVersion(id, Number(version))
      .then(setResult)
      .catch(() => setError(true));
  }, [id, version]);

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">No such snapshot.</p>
      </div>
    );
  }
  if (!result) {
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading snapshot…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <Link
        to={`/reviews/${id}/audit`}
        className="text-label-caps uppercase text-ink-muted-light hover:text-accent"
      >
        ← Audit trail
      </Link>
      <div className="mt-4 rounded-sm border border-accent-border bg-accent-container px-4 py-2 font-mono text-[12px] text-on-accent-container">
        Read-only archived snapshot · v{version}
      </div>
      <div className="mt-4">
        <ReportView result={result} />
      </div>
    </div>
  );
}
