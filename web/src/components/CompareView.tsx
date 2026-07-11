import type { AssetComparison } from "../lib/types";

// Side-by-side profile. Operational facts only — phase, pivotal trial, enrollment,
// geography, timing. Pooled meta-analysis evidence is deliberately NOT shown on the
// market-intelligence surface; it lives in the review pages.
export function CompareView({ comparison }: { comparison: AssetComparison }) {
  const { assets, rows } = comparison;

  return (
    <div className="overflow-x-auto rounded-md hairline bg-card-light">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="hairline-b text-label-caps uppercase text-ink-muted-light">
            <th className="px-4 py-2.5 text-left font-semibold" />
            {assets.map((a) => (
              <th key={a} className="px-4 py-2.5 text-left font-semibold text-ink-light">
                {a}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="hairline-b">
              <td className="px-4 py-2.5 text-ink-muted-light">{row.label}</td>
              {row.values.map((v, i) => (
                <td key={i} className="px-4 py-2.5 font-mono text-ink-light">
                  {v}
                  {row.more[i] && (
                    <span className="ml-1 text-[11px] font-sans text-ink-muted-light">(more)</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
