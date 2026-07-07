import { ForestPlot } from "./ForestPlot";
import { ProvenancePopover } from "./ProvenancePopover";
import type { ReviewResult } from "../lib/types";

function i2Band(i2: number): string {
  if (i2 <= 40) return "might not be important";
  if (i2 <= 60) return "moderate";
  if (i2 <= 90) return "substantial";
  return "considerable";
}

// The pooled-answer report. Presentational: given a ReviewResult, renders the
// headline estimate, clinical conclusion, heterogeneity, forest plot, and the
// evidence ledger with per-row provenance.
export function ReportView({ result }: { result: ReviewResult }) {
  if (!result.pool) {
    return (
      <p className="font-mono text-[13px] text-ink-muted-light">
        Too few valid trials to pool — abstaining. {result.summary}
      </p>
    );
  }
  const { pool, summary, extractions } = result;

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
        Pooled answer
      </p>

      <div className="mt-3 flex items-baseline gap-4">
        <span className="font-mono text-[40px] font-medium tracking-tight text-ink-light">
          {pool.measure} {pool.estimate.toFixed(2)}
        </span>
        <span className="font-mono text-[16px] text-ink-muted-light">
          95% CI {pool.ci_low.toFixed(2)}–{pool.ci_high.toFixed(2)}
        </span>
        <span className="ml-auto rounded-full border border-hairline-light px-3 py-1 font-mono text-[11px] text-ink-muted-light">
          {pool.ci_method.toUpperCase()} · {pool.method} · {pool.engine}
        </span>
      </div>

      <p className="mt-6 border-l-2 border-accent pl-4 font-serif text-[18px] leading-7 text-ink-light">
        {summary}
      </p>

      <div className="mt-8 grid grid-cols-4 gap-px overflow-hidden rounded-md border border-hairline-light bg-hairline-light">
        {[
          ["Studies", String(pool.k)],
          ["I²", `${pool.i2.toFixed(0)}% · ${i2Band(pool.i2)}`],
          ["τ²", pool.tau2.toFixed(3)],
          [
            "Prediction",
            pool.prediction_low != null
              ? `${pool.prediction_low.toFixed(2)}–${pool.prediction_high!.toFixed(2)}`
              : "n/a",
          ],
        ].map(([k, v]) => (
          <div key={k} className="bg-card-light p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
              {k}
            </p>
            <p className="mt-1 font-mono text-[14px] text-ink-light">{v}</p>
          </div>
        ))}
      </div>

      <section className="mt-8 rounded-md border border-hairline-light bg-card-light p-6">
        <h2 className="mb-4 text-[13px] font-medium text-ink-light">Forest plot</h2>
        <ForestPlot pool={pool} />
      </section>

      {pool.notes.length > 0 && (
        <ul className="mt-4 flex flex-col gap-1">
          {pool.notes.map((n, i) => (
            <li key={i} className="font-mono text-[12px] text-risk-some">
              ⚠ {n}
            </li>
          ))}
        </ul>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-[13px] font-medium text-ink-light">
          Evidence ledger — every number traced to its source
        </h2>
        <div className="overflow-hidden rounded-md border border-hairline-light">
          {extractions.map((e) => (
            <div
              key={e.study_id}
              className="flex items-start gap-4 border-b border-hairline-light bg-card-light p-4 last:border-0"
            >
              <span className="w-28 shrink-0 font-mono text-[12px] text-ink-muted-light">
                {e.study_id}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-ink-light">{e.label}</p>
                <p className="mt-1 font-mono text-[12px] text-ink-muted-light">
                  {e.provenance[0]?.snippet}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-[13px] text-ink-light">
                  {e.flagged ? "flagged" : `HR ${e.hr}`}
                </span>
                {!e.flagged && <ProvenancePopover provenance={e.provenance} />}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
