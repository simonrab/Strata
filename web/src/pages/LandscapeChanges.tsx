import { useEffect, useState } from "react";
import { getLandscapeChanges } from "../lib/api";
import type { LandscapeDiff } from "../lib/types";
import { ChangeFeed } from "../components/ChangeFeed";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/Loading";
import { MIN_YEAR, MAX_YEAR } from "../components/PipelineBoard";

// "What moved" — the market-intelligence change-feed, between a `since` date and now.
export function LandscapeChanges() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [sinceYear, setSinceYear] = useState(MAX_YEAR - 2);
  const [diff, setDiff] = useState<LandscapeDiff | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const since = `${sinceYear}-01-01`;

  useEffect(() => {
    setLoading(true);
    getLandscapeChanges(condition, since, null)
      .then((d) => {
        setDiff(d);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, sinceYear]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6">
        <h1 className="font-sans text-display-lg text-ink-light">What changed</h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          Every competitive move in a condition, since a date you choose.
        </p>
      </div>

      <form
        className="mb-5 flex flex-wrap items-center gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setCondition(input.trim() || condition);
        }}
      >
        <div className="flex items-center gap-2 rounded-sm hairline bg-card-light px-3 py-2">
          <Icon name="search" size={16} className="text-ink-muted-light" />
          <input
            aria-label="condition"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="w-64 bg-transparent text-[14px] text-ink-light outline-none"
            placeholder="Condition, e.g. Obesity"
          />
        </div>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Show changes
        </button>
      </form>

      <div className="mb-6 flex items-center gap-4 rounded-md hairline bg-card-light px-4 py-3">
        <Icon name="history" size={18} className="text-ink-muted-light" />
        <span className="text-label-caps uppercase text-ink-muted-light">Since</span>
        <input
          type="range"
          aria-label="since year"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={sinceYear}
          onChange={(e) => setSinceYear(Number(e.target.value))}
          className="flex-1 accent-accent"
        />
        <span className="w-24 text-right font-mono text-[13px] text-ink-light">Jan {sinceYear}</span>
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load changes. Is the backend running on :8000?
        </p>
      )}
      {loading && !diff && <LoadingState label="Diffing the landscape…" />}
      {diff && <ChangeFeed diff={diff} />}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Moves are computed by reconstructing the landscape at two dates — advances, new programs,
        readouts, and source conflicts — each traced to its source.
      </p>
    </div>
  );
}
