import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { compareAssets } from "../lib/api";
import type { AssetComparison } from "../lib/types";
import { CompareView } from "../components/CompareView";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/Loading";

// Side-by-side profile of two assets. Operational facts compare; efficacy abstains.
export function AssetCompare() {
  const [params, setParams] = useSearchParams();
  const [a, setA] = useState(params.get("a") ?? "Tirzepatide");
  const [b, setB] = useState(params.get("b") ?? "Semaglutide");
  const [indication, setIndication] = useState(params.get("indication") ?? "");
  const [comparison, setComparison] = useState<AssetComparison | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const qa = params.get("a");
  const qb = params.get("b");
  const qi = params.get("indication");

  useEffect(() => {
    if (!qa || !qb) return;
    setLoading(true);
    compareAssets([qa, qb], qi || undefined)
      .then((c) => {
        setComparison(c);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [qa, qb, qi]);

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-6">
        <h1 className="font-sans text-display-lg text-ink-light">Compare assets</h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          Two assets side by side on stage, scale, geography, and timing.
        </p>
      </div>

      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const next = new URLSearchParams();
          next.set("a", a.trim());
          next.set("b", b.trim());
          if (indication.trim()) next.set("indication", indication.trim());
          setParams(next);
        }}
      >
        <label className="text-[13px] text-ink-muted-light">
          Asset A
          <input
            aria-label="asset a"
            value={a}
            onChange={(e) => setA(e.target.value)}
            className="mt-1 block w-48 rounded-sm hairline bg-card-light px-3 py-2 text-[14px] text-ink-light outline-none"
          />
        </label>
        <label className="text-[13px] text-ink-muted-light">
          Asset B
          <input
            aria-label="asset b"
            value={b}
            onChange={(e) => setB(e.target.value)}
            className="mt-1 block w-48 rounded-sm hairline bg-card-light px-3 py-2 text-[14px] text-ink-light outline-none"
          />
        </label>
        <label className="text-[13px] text-ink-muted-light">
          Indication (optional)
          <input
            aria-label="indication"
            value={indication}
            onChange={(e) => setIndication(e.target.value)}
            className="mt-1 block w-48 rounded-sm hairline bg-card-light px-3 py-2 text-[14px] text-ink-light outline-none"
            placeholder="e.g. Obesity"
          />
        </label>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Compare
        </button>
      </form>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the comparison. Is the backend running on :8000?
        </p>
      )}
      {loading && !comparison && <LoadingState label="Building the side-by-side…" />}
      {comparison && <CompareView comparison={comparison} />}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Operational facts only — stage, trial, enrollment, geography, and timing, read from
        ClinicalTrials.gov. Pooled efficacy evidence lives in the meta-analysis review pages.
      </p>
    </div>
  );
}
