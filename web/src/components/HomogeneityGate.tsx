import { useState } from "react";
import { Icon } from "./Icon";
import { postDiversityDecision } from "../lib/api";
import type { DiversityAssessment, ReviewResult } from "../lib/types";

const PICO_LABEL: Record<string, string> = {
  population: "Population",
  intervention: "Intervention",
  comparator: "Comparator",
  outcome: "Outcome",
};

function judgmentStyle(judgment: string): { dot: string; label: string } {
  if (judgment === "divergent") return { dot: "bg-risk-high", label: "Divergent" };
  if (judgment === "mixed") return { dot: "bg-risk-some", label: "Mixed" };
  if (judgment === "similar") return { dot: "bg-risk-low", label: "Similar" };
  return { dot: "bg-outline", label: "Not assessed" };
}

// The homogeneity gate: when a review is withheld because the trials are
// clinically diverse or statistically heterogeneous, this surfaces the four
// PICO judgments plus the I² band and lets a reviewer confirm that the trials
// are combinable — which lifts the gate and pools them.
export function HomogeneityGate({
  reviewId,
  diversity,
  onConfirmed,
}: {
  reviewId: string;
  diversity: DiversityAssessment;
  onConfirmed: (r: ReviewResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      onConfirmed(await postDiversityDecision(reviewId, "Confirmed clinically combinable"));
    } catch {
      setError("Could not record the confirmation.");
      setBusy(false);
    }
  };

  return (
    <section className="rounded-md border border-risk-some bg-risk-some-container/40 p-5">
      <div className="flex items-start gap-3">
        <Icon name="warning" size={22} fill className="mt-0.5 shrink-0 text-risk-some" />
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold text-ink-light">
            Pooling withheld — confirm the trials are combinable
          </h2>
          <p className="mt-1 font-serif text-[14px] leading-6 text-ink-muted-light">
            {diversity.rationale}
          </p>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {diversity.domains.map((d) => {
              const s = judgmentStyle(d.judgment);
              return (
                <div key={d.key} className="rounded-sm hairline bg-card-light p-3">
                  <p className="text-label-caps uppercase text-ink-muted-light">
                    {PICO_LABEL[d.key] ?? d.key}
                  </p>
                  <p className="mt-1.5 flex items-center gap-1.5 text-[13px] text-ink-light">
                    <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
                    {s.label}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <span className="font-mono text-[12px] text-ink-muted-light">
              Statistical heterogeneity: I²{" "}
              {diversity.i2 != null ? `${diversity.i2.toFixed(0)}%` : "—"} ({diversity.i2_band})
            </span>
            <button
              onClick={confirm}
              disabled={busy}
              className="ml-auto inline-flex items-center gap-1.5 rounded-sm bg-ink-light px-5 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90 disabled:opacity-40"
            >
              <Icon name="check" size={18} />
              {busy ? "Pooling…" : "Confirm and pool unlike trials"}
            </button>
          </div>
          {error && <p className="mt-2 font-mono text-[12px] text-risk-high">{error}</p>}
        </div>
      </div>
    </section>
  );
}
