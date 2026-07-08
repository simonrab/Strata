import type { ReviewDiff, ReviewResult } from "../lib/types";

function fmt(n: number | null | undefined): string {
  return n == null ? "—" : n.toFixed(2);
}

// The "Parameter Shifts" panel: what re-pooling with the new trial changed,
// version over version, plus a plain-language verdict. Every number is read from
// the stored pools and the diff flags — never computed here.
export function DiffTable({
  diff,
  previous,
  current,
}: {
  diff: ReviewDiff;
  previous: ReviewResult | null;
  current: ReviewResult | null;
}) {
  const measure = current?.pool?.measure ?? previous?.pool?.measure ?? "HR";

  const rows = [
    {
      label: `${measure} (point estimate)`,
      prev: fmt(diff.estimate_prev),
      curr: fmt(diff.estimate_curr),
      changed: diff.estimate_prev !== diff.estimate_curr,
    },
    {
      label: "Heterogeneity (I²)",
      prev: previous?.pool ? `${previous.pool.i2.toFixed(0)}%` : "—",
      curr: current?.pool ? `${current.pool.i2.toFixed(0)}%` : "—",
      changed: (previous?.pool?.i2 ?? null) !== (current?.pool?.i2 ?? null),
    },
    {
      label: "GRADE certainty",
      prev: previous?.grade ? previous.grade.certainty.replace("_", " ") : "—",
      curr: current?.grade ? current.grade.certainty.replace("_", " ") : "—",
      changed:
        (previous?.grade?.certainty ?? null) !== (current?.grade?.certainty ?? null),
    },
    {
      label: "Trials pooled (k)",
      prev: String(diff.k_prev),
      curr: String(diff.k_curr),
      changed: diff.k_prev !== diff.k_curr,
    },
  ];

  const pool = current?.pool;
  const significant = pool ? pool.ci_high < 1 || pool.ci_low > 1 : false;
  const reduced = pool ? pool.estimate < 1 : false;
  const verdict = diff.conclusion_changed
    ? "Conclusion moved."
    : !pool
    ? "Too few valid trials to pool — abstaining."
    : significant && reduced
    ? "Benefit holds — estimate refined."
    : significant
    ? "Effect holds — estimate refined."
    : "No statistically significant effect.";

  return (
    <section className="overflow-hidden rounded-md border border-hairline-light bg-card-light">
      <div className="flex items-center justify-between border-b border-hairline-light bg-surface-container-low p-3">
        <h3 className="text-[13px] font-medium text-ink-light">Parameter Shifts</h3>
        <span className="font-mono text-[11px] text-ink-muted-light">
          v{diff.previous_version} → v{diff.current_version}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-left">
          <thead>
            <tr className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
              <th className="p-3">Metric</th>
              <th className="p-3 text-right">v{diff.previous_version}</th>
              <th className="w-8 p-3" />
              <th className="p-3 text-right text-secondary">v{diff.current_version}</th>
            </tr>
          </thead>
          <tbody className="font-mono text-[13px]">
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-hairline-light">
                <td className="p-3 font-sans text-ink-light">{r.label}</td>
                <td className="p-3 text-right text-ink-muted-light">{r.prev}</td>
                <td className="p-3 text-center text-ink-muted-light">→</td>
                <td
                  className={`p-3 text-right ${
                    r.changed ? "font-medium text-secondary" : "text-ink-light"
                  }`}
                >
                  {r.curr}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-1 border-t border-hairline-light bg-surface-container-low p-4">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
          Synthesis verdict
        </span>
        <p className="flex items-center gap-2 font-serif text-[18px] text-ink-light">
          <span className={diff.conclusion_changed ? "text-risk-some" : "text-secondary"}>
            {diff.conclusion_changed ? "⚠" : "✓"}
          </span>
          {verdict}
        </p>
      </div>
    </section>
  );
}
