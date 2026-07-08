import { useState } from "react";
import { useParams } from "react-router-dom";
import { getVersion, postUpdate } from "../lib/api";
import { DiffTable } from "../components/DiffTable";
import { ForestPlot } from "../components/ForestPlot";
import type { ReviewDiff, ReviewResult } from "../lib/types";

// The living demo's held-out trial: AMPLITUDE-O (efpeglenatide, 2021), the most
// recent GLP-1 cardiovascular outcome trial. Injecting it takes the review from
// the 7-trial baseline to today's published 8-trial answer.
const NEW_TRIAL = { id: "NCT03496298", label: "AMPLITUDE-O" };

export function Updates() {
  const { id = "" } = useParams();
  const [diff, setDiff] = useState<ReviewDiff | null>(null);
  const [previous, setPrevious] = useState<ReviewResult | null>(null);
  const [current, setCurrent] = useState<ReviewResult | null>(null);
  const [injecting, setInjecting] = useState(false);
  const [error, setError] = useState(false);

  async function inject() {
    setInjecting(true);
    setError(false);
    try {
      const d = await postUpdate(id, NEW_TRIAL.id);
      const [prev, curr] = await Promise.all([
        getVersion(id, d.previous_version),
        getVersion(id, d.current_version),
      ]);
      setDiff(d);
      setPrevious(prev);
      setCurrent(curr);
    } catch {
      setError(true);
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-10">
      <div>
        <p className="text-label-caps uppercase text-outline">
          Living diff
        </p>
        <h1 className="mt-1 font-sans text-display-lg text-ink-light">
          Living Diff: Meta-Analysis Update
        </h1>
        <p className="mt-1 text-[14px] text-ink-muted-light">
          Recompute the pooled answer when a new trial lands, and see what moved —
          the estimate, the heterogeneity, and whether the conclusion changed.
        </p>
      </div>

      {/* New-trial notification banner */}
      <div className="flex flex-col justify-between gap-3 rounded-md border border-accent-border bg-accent-container p-4 md:flex-row md:items-center">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <span className="font-mono text-[12px] font-semibold uppercase tracking-wider text-on-accent-container">
            New results posted · {NEW_TRIAL.id} · {NEW_TRIAL.label} (2021)
          </span>
        </div>
        <button
          onClick={inject}
          disabled={injecting}
          className="rounded-sm bg-accent px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {injecting ? "Re-pooling…" : `Inject ${NEW_TRIAL.label}`}
        </button>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Update failed. Seed the demo baseline first, then try again.
        </p>
      )}

      {!diff && !injecting && (
        <p className="rounded-md hairline bg-surface-container-low px-4 py-3 text-[13px] text-ink-muted-light">
          Inject the new trial to re-run the pooled analysis and compare it against
          the current version.
        </p>
      )}

      {diff && current && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <DiffTable diff={diff} previous={previous} current={current} />
          </div>
          <section className="rounded-md hairline bg-card-light p-6 lg:col-span-6">
            <h2 className="mb-4 text-[13px] font-medium text-ink-light">
              Updated forest plot
            </h2>
            {current.pool ? (
              <ForestPlot pool={current.pool} highlightStudyIds={diff.added_trials} />
            ) : (
              <p className="font-mono text-[12px] text-ink-muted-light">
                Too few valid trials to pool — abstaining.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
