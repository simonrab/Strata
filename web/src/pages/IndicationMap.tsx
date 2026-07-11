import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getIndicationMap } from "../lib/api";
import type { IndicationMap as IMap, Source } from "../lib/types";
import { PHASE_LABEL } from "../lib/types";
import { Icon } from "../components/Icon";
import { SourceToggle, loadSources } from "../components/SourceToggle";

const PHASE_ORDER = ["preclinical", "phase_1", "phase_1_2", "phase_2", "phase_2_3", "phase_3", "phase_4", "filed", "approved"];

export function IndicationMap() {
  const { name = "" } = useParams();
  const [sources, setSources] = useState<Source[]>(loadSources());
  const [map, setMap] = useState<IMap | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getIndicationMap(name, sources)
      .then((m) => { setMap(m); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [name, sources]);

  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">{decodeURIComponent(name)}</h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            The indication, broken into the sub-populations trials actually enrol.
          </p>
        </div>
        <SourceToggle value={sources} onChange={setSources} />
      </div>

      {error && <p className="mt-6 font-mono text-[13px] text-risk-high">Could not load the indication map.</p>}
      {loading && !map && <p className="mt-6 font-mono text-[13px] text-ink-muted-light">Mapping sub-populations…</p>}

      {map && map.nodes.length === 0 && !loading && (
        <p className="mt-6 text-[14px] text-ink-muted-light">No trials found for this indication.</p>
      )}

      {map && map.nodes.length > 0 && (
        <div className="mt-6 space-y-4">
          {map.nodes.map((node) => {
            const maxStage = Math.max(1, ...Object.values(node.stage_distribution));
            return (
              <div key={node.signature} className="rounded-md hairline bg-card-light p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-headline-md text-ink-light">{node.label}</h3>
                    <p className="mt-0.5 text-[12px] text-ink-muted-light">
                      {node.trial_count} trials · {node.assets.length} assets · {node.countries.length} countries
                    </p>
                  </div>
                </div>

                <div className="mt-3 grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="mb-1 text-label-caps uppercase text-ink-muted-light">Assets</p>
                    <div className="flex flex-wrap gap-1">
                      {node.assets.map((a) => (
                        <Link
                          key={a}
                          to={`/asset/${encodeURIComponent(a)}`}
                          className="rounded-sm bg-surface-container-high px-2 py-0.5 text-[12px] text-ink-light hover:text-accent"
                        >
                          {a}
                        </Link>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-label-caps uppercase text-ink-muted-light">Stage distribution</p>
                    <div className="space-y-1">
                      {PHASE_ORDER.filter((p) => node.stage_distribution[p]).map((p) => (
                        <div key={p} className="flex items-center gap-2 text-[12px]">
                          <span className="w-16 text-ink-muted-light">{PHASE_LABEL[p as never]}</span>
                          <span
                            className="h-2 rounded-sm bg-accent"
                            style={{ width: `${(node.stage_distribution[p] / maxStage) * 120}px` }}
                          />
                          <span className="font-mono text-ink-muted-light">{node.stage_distribution[p]}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="mt-6 flex items-center gap-2 text-[12px] text-ink-muted-light">
        <Icon name="info" size={16} />
        Sub-populations are read by Claude from each trial's eligibility criteria; without a
        model key they fall back to the base indication.
      </p>
    </div>
  );
}
