import { Link } from "react-router-dom";
import { useReview } from "../lib/review";
import { ForestPlot } from "../components/ForestPlot";

function i2Band(i2: number): string {
  if (i2 <= 40) return "might not be important";
  if (i2 <= 60) return "moderate";
  if (i2 <= 90) return "substantial";
  return "considerable";
}

export function Report() {
  const { result } = useReview();

  if (!result || !result.pool) {
    return (
      <div className="mx-auto max-w-3xl px-8 py-12">
        <p className="font-mono text-[13px] text-ink-muted-light">
          No result yet. <Link className="text-[#2563eb] underline" to="/">Start a review</Link>.
        </p>
      </div>
    );
  }

  const { pool, summary, extractions } = result;

  return (
    <div className="mx-auto max-w-4xl px-8 py-12">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
        Pooled answer
      </p>

      {/* Headline stat */}
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

      {/* Clinical conclusion */}
      <p className="mt-6 border-l-2 border-[#2563eb] pl-4 font-serif text-[18px] leading-7 text-ink-light">
        {summary}
      </p>

      {/* Heterogeneity strip */}
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

      {/* Forest plot */}
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

      {/* Evidence ledger with provenance */}
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
              <span className="font-mono text-[12px] text-ink-muted-light w-28 shrink-0">
                {e.study_id}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-ink-light">{e.label}</p>
                <p className="mt-1 font-mono text-[12px] text-ink-muted-light">
                  {e.provenance[0]?.snippet}
                </p>
              </div>
              <span className="font-mono text-[13px] text-ink-light shrink-0">
                {e.flagged ? "flagged" : `HR ${e.hr}`}
              </span>
            </div>
          ))}
        </div>
      </section>

      <div className="mt-8">
        <Link
          to="/"
          className="rounded-sm border border-hairline-light px-4 py-2 text-[13px] text-ink-light hover:bg-surface-container-low"
        >
          New review
        </Link>
      </div>
    </div>
  );
}
