import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCompanyPipeline } from "../lib/api";
import type { CompanyPipeline as Pipeline, Source } from "../lib/types";
import { Icon } from "../components/Icon";
import {
  AsOfSlider,
  IndicationFilter,
  MAX_YEAR,
  PipelineBoard,
} from "../components/PipelineBoard";
import { LoadingState } from "../components/Loading";
import { SourceToggle, loadSources } from "../components/SourceToggle";

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-md hairline bg-card-light px-4 py-2 text-center">
      <div className="font-mono text-[20px] text-ink-light">{value}</div>
      <div className="text-label-caps uppercase text-ink-muted-light">{label}</div>
    </div>
  );
}

export function CompanyPipeline() {
  const { name = "" } = useParams();
  const sponsor = decodeURIComponent(name);
  const [year, setYear] = useState(MAX_YEAR);
  const [indication, setIndication] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>(loadSources());
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const asOf = year >= MAX_YEAR ? null : `${year}-12-31`;

  useEffect(() => {
    setLoading(true);
    setIndication(null);
    getCompanyPipeline(name, asOf, sources)
      .then((p) => {
        setPipeline(p);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, year, sources]);

  // Indications that actually have a cell, so the filter never offers an empty one.
  const indications = useMemo(() => {
    if (!pipeline) return [];
    const used = new Set((pipeline.cells ?? []).map((c) => c.indication));
    return pipeline.indications.filter((ind) => used.has(ind));
  }, [pipeline]);

  const trialCount = pipeline?.cells.length ?? 0;

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <Link
        to="/landscape"
        className="mb-4 inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
      >
        <Icon name="chevron_left" size={14} /> Landscape
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">{sponsor}</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">The pipeline.</p>
        </div>
        <SourceToggle value={sources} onChange={setSources} />
      </div>

      {pipeline && pipeline.assets.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-3">
          <Stat value={pipeline.assets.length} label="Assets" />
          <Stat value={trialCount} label="Programs" />
          <Stat value={indications.length} label="Indications" />
        </div>
      )}

      <div className="mt-6">
        <AsOfSlider year={year} onChange={setYear} />
      </div>

      {error && (
        <p className="font-mono text-[13px] text-risk-high">
          Could not load the pipeline. Is the backend running on :8000?
        </p>
      )}

      {loading && !pipeline && <LoadingState label="Mapping the pipeline…" />}

      {pipeline && pipeline.assets.length === 0 && !loading && (
        <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
          No development activity found for <span className="font-medium">{sponsor}</span>
          {asOf ? ` as of ${asOf}.` : "."} Sponsor names come straight from ClinicalTrials.gov and
          are not normalized, so a company may appear under more than one spelling.
        </div>
      )}

      {pipeline && pipeline.assets.length > 0 && (
        <>
          <IndicationFilter
            indications={indications}
            active={indication}
            onSelect={setIndication}
          />
          <PipelineBoard
            cells={pipeline.cells}
            asOf={pipeline.as_of}
            indication={indication}
          />
        </>
      )}

      {pipeline?.notes.map((note, i) => (
        <p key={i} className="mt-4 flex items-center gap-2 text-[12px] text-ink-muted-light">
          <Icon name="info" size={16} /> {note}
        </p>
      ))}
    </div>
  );
}
