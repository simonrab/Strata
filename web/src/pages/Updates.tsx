import { useState } from "react";
import { useParams } from "react-router-dom";
import { checkUpdates, getVersion, postUpdate } from "../lib/api";
import { DiffTable } from "../components/DiffTable";
import { ForestPlot } from "../components/ForestPlot";
import type { ReviewDiff, ReviewResult, TrialCandidate } from "../lib/types";

export function Updates() {
  const { id = "" } = useParams();
  const [candidates, setCandidates] = useState<TrialCandidate[] | null>(null);
  const [checking, setChecking] = useState(false);
  const [diff, setDiff] = useState<ReviewDiff | null>(null);
  const [previous, setPrevious] = useState<ReviewResult | null>(null);
  const [current, setCurrent] = useState<ReviewResult | null>(null);
  const [injectingId, setInjectingId] = useState<string | null>(null);
  const [error, setError] = useState(false);

  // Discovery: re-run the saved question's PICO search and diff against the ids
  // already pooled. This is the living claim made real — genuinely-new trials,
  // not a hard-coded banner.
  async function check() {
    setChecking(true);
    setError(false);
    try {
      setCandidates(await checkUpdates(id));
    } catch {
      setError(true);
    } finally {
      setChecking(false);
    }
  }

  // The reviewer's decision to update: inject one discovered trial, re-pool, diff.
  async function inject(nctId: string) {
    setInjectingId(nctId);
    setError(false);
    try {
      const d = await postUpdate(id, nctId);
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
      setInjectingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-10">
      <div>
        <p className="text-label-caps uppercase text-outline">Living diff</p>
        <h1 className="mt-1 font-sans text-display-lg text-ink-light">
          Living Diff: Meta-Analysis Update
        </h1>
        <p className="mt-1 text-[14px] text-ink-muted-light">
          Re-search ClinicalTrials.gov for trials that have landed since the last
          run, then recompute the pooled answer and see what moved: the estimate,
          the heterogeneity, and whether the conclusion changed.
        </p>
      </div>

      {/* Discovery: check for genuinely-new trials on demand. */}
      <div className="flex flex-col justify-between gap-3 rounded-md border border-accent-border bg-accent-container p-4 md:flex-row md:items-center">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <span className="font-mono text-[12px] font-semibold uppercase tracking-wider text-on-accent-container">
            Re-search this question for new readouts
          </span>
        </div>
        <button
          onClick={check}
          disabled={checking}
          className="rounded-sm bg-accent px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {checking ? "Checking…" : "Check for new trials"}
        </button>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Check failed. Seed the demo baseline first, then try again.
        </p>
      )}

      {candidates !== null && candidates.length === 0 && (
        <p className="rounded-md hairline bg-surface-container-low px-4 py-3 text-[13px] text-ink-muted-light">
          No new trials since last run. The pooled answer is current.
        </p>
      )}

      {candidates && candidates.length > 0 && (
        <div className="rounded-md hairline bg-card-light p-4">
          <p className="mb-3 text-[13px] font-medium text-ink-light">
            {candidates.length} new{" "}
            {candidates.length === 1 ? "trial" : "trials"} found — inject one to
            re-pool and diff.
          </p>
          <ul className="space-y-2">
            {candidates.map((c) => (
              <li
                key={c.nct_id}
                className="flex flex-col justify-between gap-2 rounded-sm hairline bg-surface-container-low px-3 py-2 md:flex-row md:items-center"
              >
                <div className="flex flex-col">
                  <span className="font-mono text-[12px] text-accent">
                    {c.nct_id}
                  </span>
                  <span className="text-[13px] text-ink-light">{c.title}</span>
                </div>
                <button
                  onClick={() => inject(c.nct_id)}
                  disabled={injectingId !== null}
                  className="shrink-0 rounded-sm bg-accent px-3 py-1.5 text-[12px] font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {injectingId === c.nct_id ? "Re-pooling…" : "Inject"}
                </button>
              </li>
            ))}
          </ul>
        </div>
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
                Too few valid trials to pool. Abstaining.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
