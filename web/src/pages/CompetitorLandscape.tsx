import { useEffect, useMemo, useState } from "react";
import { getLandscape } from "../lib/api";
import type { Landscape } from "../lib/types";
import { Icon } from "../components/Icon";
import {
  AsOfSlider,
  IndicationFilter,
  MAX_YEAR,
  PipelineBoard,
} from "../components/PipelineBoard";
import { LoadingState } from "../components/Loading";

export function CompetitorLandscape() {
  const [input, setInput] = useState("Obesity");
  const [condition, setCondition] = useState("Obesity");
  const [year, setYear] = useState(MAX_YEAR);
  const [indication, setIndication] = useState<string | null>(null);
  const [landscape, setLandscape] = useState<Landscape | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const asOf = year >= MAX_YEAR ? null : `${year}-12-31`;

  useEffect(() => {
    setLoading(true);
    // A fresh condition may not carry the previously selected indication.
    setIndication(null);
    getLandscape(condition, asOf)
      .then((ls) => {
        setLandscape(ls);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condition, year]);

  // Indications that actually have a cell, in the landscape's declared order.
  const indications = useMemo(() => {
    if (!landscape) return [];
    const used = new Set((landscape.cells ?? []).map((c) => c.indication));
    return landscape.indications.filter((ind) => used.has(ind));
  }, [landscape]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">Competitive Landscape</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            Every asset by its stage of development.
          </p>
        </div>
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
            placeholder="Condition, e.g. Type 2 Diabetes"
          />
        </div>
        <button
          type="submit"
          className="rounded-sm bg-ink-light px-4 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
        >
          Map
        </button>
      </form>

      <AsOfSlider year={year} onChange={setYear} />

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the landscape. Is the backend running on :8000?
        </p>
      )}

      {loading && !landscape && <LoadingState label="Mapping the landscape…" />}

      {landscape && landscape.assets.length === 0 && !loading && (
        <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
          No development activity found for <span className="font-medium">{condition}</span>
          {asOf ? ` as of ${asOf}.` : "."}
        </div>
      )}

      {landscape && landscape.assets.length > 0 && (
        <>
          <IndicationFilter
            indications={indications}
            active={indication}
            onSelect={setIndication}
          />
          <PipelineBoard
            cells={landscape.cells}
            asOf={landscape.as_of}
            condition={condition}
            indication={indication}
          />
        </>
      )}

      <p className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Each drug's phase is read from ClinicalTrials.gov, and every stage links back to its source
        trial. Click a sponsor to see that company's entire pipeline.
      </p>
    </div>
  );
}
