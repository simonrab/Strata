import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview, postScreeningDecision } from "../lib/api";
import type { EligibilityDecision, ReviewResult } from "../lib/types";

function Disposition({ decision }: { decision: string }) {
  const included = decision === "included";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        included
          ? "bg-risk-low-container text-risk-low"
          : "bg-risk-high text-white"
      }`}
    >
      {included ? "Included" : "Excluded"}
    </span>
  );
}

// Who made the call: Claude's clinical read, the deterministic filter / keyless
// auto-include, or a reviewer's sign-off — surfaced so the funnel is never taken
// on faith.
function sourceLabel(d: EligibilityDecision): string {
  if (d.confirmed && !d.by_claude) return "Reviewer";
  if (d.by_claude) return "Claude";
  return "Automatic";
}

export function Screening() {
  const { id = "" } = useParams();
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    getReview(id)
      .then(setReview)
      .catch(() => setError(true));
  }, [id]);

  async function decide(studyId: string, decision: "included" | "excluded") {
    setSaving(studyId);
    try {
      const updated = await postScreeningDecision(id, { study_id: studyId, decision });
      setReview(updated);
    } finally {
      setSaving(null);
    }
  }

  if (error)
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">No such review.</p>
      </div>
    );
  if (!review)
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading screening…</p>
      </div>
    );

  const decisions = review.screening ?? [];
  const included = decisions.filter((d) => d.decision === "included").length;
  const excluded = decisions.length - included;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-10">
      <div>
        <p className="text-label-caps uppercase text-outline">Eligibility screening</p>
        <h1 className="mt-1 font-sans text-display-lg text-ink-light">Screening</h1>
        <p className="mt-1 text-[14px] text-ink-muted-light">
          Each candidate is screened against the question's PICO before pooling.
          Confirm the call or override it — a re-include re-fetches and re-pools the
          trial. {included} included · {excluded} excluded.
        </p>
      </div>

      {decisions.length === 0 ? (
        <p className="rounded-sm hairline bg-surface-container-low px-4 py-3 font-mono text-[12px] text-ink-muted-light">
          No screening decisions recorded for this review.
        </p>
      ) : (
        <section className="overflow-x-auto rounded-md hairline bg-card-light">
          <div className="grid min-w-[820px] grid-cols-12 gap-3 hairline-b bg-surface-container-low p-3 text-label-caps uppercase text-ink-muted-light">
            <div className="col-span-2">Trial</div>
            <div className="col-span-2">Disposition</div>
            <div className="col-span-5">Reason</div>
            <div className="col-span-3 text-right">Action</div>
          </div>
          {decisions.map((d) => (
            <div
              key={d.study_id}
              data-testid="screen-row"
              className="grid min-w-[820px] grid-cols-12 items-start gap-3 hairline-b p-3 last:border-0 hover:bg-surface-container-low"
            >
              <div className="col-span-2">
                <p className="font-mono text-[13px] text-ink-light">{d.study_id}</p>
                <p className="text-[11px] uppercase tracking-wider text-outline">
                  {sourceLabel(d)}
                </p>
              </div>
              <div className="col-span-2">
                <Disposition decision={d.decision} />
              </div>
              <div className="col-span-5 text-[13px] text-ink-light">
                {d.reason || <span className="text-ink-muted-light">n/a</span>}
                {d.quote?.snippet && (
                  <p className="mt-1 border-l-2 border-hairline-light pl-2 font-serif text-[12px] italic text-ink-muted-light">
                    "{d.quote.snippet}"
                  </p>
                )}
              </div>
              <div className="col-span-3 flex items-center justify-end gap-2">
                {d.confirmed ? (
                  <span className="inline-flex items-center rounded-full bg-risk-low-container px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-risk-low">
                    Confirmed
                  </span>
                ) : (
                  <button
                    onClick={() => decide(d.study_id, d.decision as "included" | "excluded")}
                    disabled={saving === d.study_id}
                    className="rounded-sm hairline px-3 py-1 text-label-caps uppercase text-ink-light hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {saving === d.study_id ? "…" : "Confirm"}
                  </button>
                )}
                {d.decision === "included" ? (
                  <button
                    onClick={() => decide(d.study_id, "excluded")}
                    disabled={saving === d.study_id}
                    className="rounded-sm border border-risk-high/40 px-3 py-1 text-label-caps uppercase text-risk-high hover:bg-risk-high/10 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Exclude
                  </button>
                ) : (
                  <button
                    onClick={() => decide(d.study_id, "included")}
                    disabled={saving === d.study_id}
                    className="rounded-sm border border-accent/40 px-3 py-1 text-label-caps uppercase text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Re-include
                  </button>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      <Link
        to={`/reviews/${id}/evidence`}
        className="inline-block text-label-caps uppercase text-ink-muted-light hover:text-accent"
      >
        Evidence ledger →
      </Link>
    </div>
  );
}
