import { useEffect, useState } from "react";
import { getMoaLandscape } from "../lib/api";
import type { MoaLandscape } from "../lib/types";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/Loading";
import { MoaView } from "../components/MoaView";

// The competitive field grouped by mechanism of action.
export function MoaClusters() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [moa, setMoa] = useState<MoaLandscape | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getMoaLandscape(condition)
      .then((m) => {
        setMoa(m);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [condition]);

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <div className="mb-6">
        <h1 className="font-sans text-display-lg text-ink-light">By mechanism</h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          The field grouped by drug class.
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
          Cluster
        </button>
      </form>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the clusters. Is the backend running on :8000?
        </p>
      )}
      {loading && !moa && <LoadingState label="Grouping by mechanism…" />}
      {moa && <MoaView moa={moa} />}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Mechanism is inferred from the drug's naming stem (or Claude when configured); assets that
        can't be classed confidently are grouped as unclassified — never a guessed class.
      </p>
    </div>
  );
}
