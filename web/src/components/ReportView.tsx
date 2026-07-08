import { ForestPlot } from "./ForestPlot";
import { ProvenancePopover } from "./ProvenancePopover";
import { Icon } from "./Icon";
import type { GradeRating, ReviewResult } from "../lib/types";

function i2Band(i2: number): string {
  if (i2 <= 40) return "might not be important";
  if (i2 <= 60) return "moderate";
  if (i2 <= 90) return "substantial";
  return "considerable";
}

const CERTAINTY: Record<GradeRating, { dots: number; dot: string; label: string }> = {
  high: { dots: 4, dot: "bg-risk-low", label: "High certainty" },
  moderate: { dots: 3, dot: "bg-accent", label: "Moderate certainty" },
  low: { dots: 2, dot: "bg-risk-some", label: "Low certainty" },
  very_low: { dots: 1, dot: "bg-risk-high", label: "Very low certainty" },
};

// The pooled-answer report, laid out as a two-pane clinical view: the synthesis
// (certainty, conclusion, estimate, forest plot) on the left, and a provenance
// rail tracing every pooled trial to its source on the right.
export function ReportView({ result }: { result: ReviewResult }) {
  if (!result.pool) {
    return (
      <p className="font-mono text-[13px] text-ink-muted-light">
        Too few valid trials to pool — abstaining. {result.summary}
      </p>
    );
  }
  const { pool, summary, extractions, grade, sensitivity } = result;
  const significant = pool.ci_high < 1 || pool.ci_low > 1;
  const certainty = grade ? CERTAINTY[grade.certainty] : null;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      {/* Main synthesis column */}
      <div className="space-y-6 lg:col-span-8">
        {/* Hero: certainty + conclusion + estimate */}
        <section className="rounded-md hairline bg-card-light p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${certainty?.dot ?? "bg-outline"}`} />
              <span className="text-label-caps uppercase text-ink-light">
                {certainty?.label ?? "Certainty pending"}
              </span>
            </div>
            <div className="flex gap-1">
              {Array.from({ length: 4 }).map((_, i) => (
                <span
                  key={i}
                  className={`h-2.5 w-2.5 rounded-sm ${
                    i < (certainty?.dots ?? 0) ? "bg-accent" : "bg-surface-container-highest"
                  }`}
                />
              ))}
            </div>
          </div>

          <p className="mt-5 font-serif text-clinical-conclusion text-ink-light">{summary}</p>

          <div className="mt-6 grid grid-cols-1 gap-px overflow-hidden rounded-md hairline bg-hairline-light sm:grid-cols-2">
            <div className="bg-card-light p-4">
              <p className="text-label-caps uppercase text-ink-muted-light">
                Pooled estimate ({pool.measure})
              </p>
              <p className="mt-2 font-mono text-display-xl text-ink-light">
                {pool.estimate.toFixed(2)}
              </p>
              <p className="mt-1 font-mono text-[13px] text-ink-muted-light">
                95% CI {pool.ci_low.toFixed(2)}–{pool.ci_high.toFixed(2)} ·{" "}
                {pool.ci_method.toUpperCase()}
              </p>
            </div>
            <div className="bg-card-light p-4">
              <p className="text-label-caps uppercase text-ink-muted-light">Evidence base</p>
              <p className="mt-2 font-mono text-display-xl text-ink-light">{pool.k}</p>
              <p className="mt-1 font-mono text-[13px] text-ink-muted-light">
                trials pooled · I² {pool.i2.toFixed(0)}% ({i2Band(pool.i2)})
              </p>
            </div>
          </div>
        </section>

        {/* Forest plot */}
        <section className="rounded-md hairline bg-card-light p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[13px] font-medium text-ink-light">Forest plot</h2>
            <span className="font-mono text-[11px] text-ink-muted-light">
              I² {pool.i2.toFixed(0)}% · τ² {pool.tau2.toFixed(4)} · Q {pool.q.toFixed(2)} (p{" "}
              {pool.q_p.toFixed(2)})
            </span>
          </div>
          <ForestPlot pool={pool} />
          {pool.notes.length > 0 && (
            <ul className="mt-4 flex flex-col gap-1">
              {pool.notes.map((n, i) => (
                <li key={i} className="font-mono text-[12px] text-risk-some">
                  ⚠ {n}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Leave-one-out sensitivity */}
        {sensitivity.length > 0 && (
          <section className="rounded-md hairline bg-card-light p-6">
            <h2 className="mb-1 text-[13px] font-medium text-ink-light">
              Leave-one-out sensitivity
            </h2>
            <p className="mb-4 text-[12px] text-ink-muted-light">
              Re-pooling with each trial removed — does the answer rest on any single trial?
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] border-collapse text-left">
                <thead>
                  <tr className="text-label-caps uppercase text-ink-muted-light">
                    <th className="pb-2 pr-4">Omitted trial</th>
                    <th className="pb-2 pr-4 text-right">{pool.measure} (95% CI)</th>
                    <th className="pb-2 pr-4 text-right">I²</th>
                    <th className="pb-2 text-right">Effect</th>
                  </tr>
                </thead>
                <tbody>
                  {sensitivity.map((r) => {
                    const rowSig = r.ci_high < 1 || r.ci_low > 1;
                    const flips = rowSig !== significant;
                    return (
                      <tr key={r.omitted_study_id} className="hairline-t">
                        <td className="py-2 pr-4 text-[13px] text-ink-light">
                          − {r.omitted_label}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-[13px] text-ink-light">
                          {r.estimate.toFixed(2)} [{r.ci_low.toFixed(2)}, {r.ci_high.toFixed(2)}]
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-[12px] text-ink-muted-light">
                          {r.i2.toFixed(0)}%
                        </td>
                        <td className="py-2 text-right">
                          {flips ? (
                            <span className="rounded-full bg-risk-some-container px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-risk-some">
                              Conclusion flips
                            </span>
                          ) : (
                            <span className="text-[11px] text-ink-muted-light">stable</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      {/* Provenance rail */}
      <aside className="lg:col-span-4">
        <section className="rounded-md hairline bg-card-light p-5">
          <div className="mb-4 flex items-center gap-2">
            <Icon name="policy" size={18} className="text-accent" />
            <h2 className="text-[13px] font-medium text-ink-light">Provenance</h2>
          </div>
          <div className="space-y-3">
            {extractions.map((e) => (
              <div key={e.study_id} className="rounded-md hairline bg-surface-container-low p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-[13px] font-medium text-ink-light">{e.label}</p>
                  {e.provenance[0]?.source_url && (
                    <a
                      href={e.provenance[0].source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-ink-muted-light hover:text-accent"
                    >
                      <Icon name="open_in_new" size={16} label="Open source record" />
                    </a>
                  )}
                </div>
                <dl className="mt-2 space-y-1 font-mono text-[11px]">
                  <div className="flex justify-between gap-2">
                    <dt className="text-ink-muted-light">ID</dt>
                    <dd className="text-ink-light">{e.study_id}</dd>
                  </div>
                  <div className="flex justify-between gap-2">
                    <dt className="text-ink-muted-light">Effect</dt>
                    <dd className="text-ink-light">
                      {e.flagged ? "flagged" : `${e.measure} ${e.hr}`}
                    </dd>
                  </div>
                </dl>
                {!e.flagged && (
                  <div className="mt-2">
                    <ProvenancePopover provenance={e.provenance} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </aside>
    </div>
  );
}
