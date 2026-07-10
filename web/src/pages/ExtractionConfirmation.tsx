import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getReview, postDecision } from "../lib/api";
import type { ReviewResult, TrialExtraction } from "../lib/types";
import { formatEffect } from "../lib/types";

export function ExtractionConfirmation() {
  const { id = "", trialId = "" } = useParams();
  const navigate = useNavigate();
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [ext, setExt] = useState<TrialExtraction | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReview(id)
      .then((r) => {
        setReview(r);
        setExt(r.extractions.find((e) => e.study_id === trialId) ?? null);
      })
      .catch(() => setError("Could not load the trial."));
  }, [id, trialId]);

  const decide = async (decision: "confirmed" | "flagged") => {
    setBusy(true);
    setError(null);
    try {
      await postDecision(id, {
        study_id: trialId,
        decision,
        reason: decision === "flagged" ? "Flagged during review" : null,
      });
      navigate(`/reviews/${id}/evidence`);
    } catch {
      setError("Could not save the decision.");
      setBusy(false);
    }
  };

  if (error && !ext) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">{error}</p>
      </div>
    );
  }
  if (!review || !ext) {
    return (
      <div className="mx-auto max-w-4xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading extraction…</p>
      </div>
    );
  }

  const prov = ext.provenance[0];

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-4 flex items-center gap-2 text-label-caps uppercase text-ink-muted-light">
        <Link to={`/reviews/${id}/evidence`} className="hover:text-accent">
          Evidence Ledger
        </Link>
        <span>›</span>
        <span className="rounded-sm bg-surface-container px-2 py-0.5 font-mono">{ext.study_id}</span>
      </div>

      <h1 className="font-sans text-display-lg text-ink-light">
        Confirm extraction
      </h1>
      <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
        {ext.label} · verify the effect estimate against the source before confirming.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <section className="overflow-hidden rounded-md hairline bg-card-light">
            <div className="hairline-b bg-surface-container-low px-5 py-3 text-[16px] font-medium text-ink-light">
              Primary outcome: {review.question.pico.outcome}
            </div>
            <div className="p-5">
              {formatEffect(ext) != null ? (
                <div className="flex items-baseline gap-4">
                  <span className="font-mono text-[32px] font-medium text-ink-light">
                    {ext.measure} {formatEffect(ext)}
                  </span>
                </div>
              ) : (
                <p className="font-mono text-[13px] italic text-risk-some">
                  {ext.flag_reason ?? "No usable effect estimate extracted."}
                </p>
              )}

              {prov && (
                <div className="mt-5 flex gap-3 hairline-t pt-4">
                  <span className="text-outline">“</span>
                  <p className="font-serif text-[14px] italic leading-6 text-ink-muted-light">
                    {prov.snippet}
                    <span className="mt-1 block font-sans text-[10px] font-semibold uppercase not-italic tracking-wider text-outline">
                      {prov.field ?? "source"} · {prov.trial_id}
                    </span>
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          {prov?.source_url && (
            <a
              href={prov.source_url}
              target="_blank"
              rel="noreferrer"
              className="block rounded-md hairline bg-card-light p-4 text-[13px] text-accent hover:bg-surface-container-high"
            >
              Open source document ↗
              <span className="mt-1 block font-mono text-[11px] text-ink-muted-light">
                ClinicalTrials.gov · structured results
              </span>
            </a>
          )}

          <div className="rounded-md hairline bg-card-light p-4">
            <p className="text-[13px] text-ink-muted-light">
              Verify the extraction against the source, then confirm or flag for review.
            </p>
            <button
              onClick={() => decide("confirmed")}
              disabled={busy}
              className="mt-4 w-full rounded-sm bg-ink-light py-3 text-[14px] font-medium text-canvas-light hover:opacity-90 disabled:opacity-40"
            >
              Confirm extraction
            </button>
            <button
              onClick={() => decide("flagged")}
              disabled={busy}
              className="mt-2 w-full rounded-sm hairline py-2 text-[12px] font-semibold uppercase tracking-wider text-ink-muted-light hover:bg-surface-container-high disabled:opacity-40"
            >
              Flag for review
            </button>
            {error && <p className="mt-2 font-mono text-[12px] text-risk-high">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
