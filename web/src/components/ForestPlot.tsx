import type { PoolResult } from "../lib/types";

// Log-scale forest plot rendered as inline SVG from pooled study rows.
// `highlightStudyIds` accents newly injected trials (the living-update view);
// omit it for the standard report and the plot renders exactly as before.
export function ForestPlot({
  pool,
  highlightStudyIds = [],
}: {
  pool: PoolResult;
  highlightStudyIds?: string[];
}) {
  const rows = pool.studies;
  const measure = pool.measure;
  const highlighted = new Set(highlightStudyIds);

  const lows = rows.map((r) => r.ci_low).concat(pool.ci_low);
  const highs = rows.map((r) => r.ci_high).concat(pool.ci_high);
  const min = Math.min(...lows, 0.5);
  const max = Math.max(...highs, 2);
  const logMin = Math.log(min);
  const logMax = Math.log(max);

  const plotLeft = 320;
  const plotRight = 560;
  const width = 720;
  const rowH = 30;
  const top = 44;
  const height = top + rows.length * rowH + 80;

  const x = (v: number) =>
    plotLeft + ((Math.log(v) - logMin) / (logMax - logMin)) * (plotRight - plotLeft);

  const ticks = [0.5, 0.7, 1, 1.5, 2].filter((t) => t >= min && t <= max);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full font-mono"
      role="img"
      aria-label="Forest plot"
    >
      {/* Column headers */}
      <text x={16} y={24} className="fill-ink-muted-light" fontSize="11" fontWeight="600">
        STUDY
      </text>
      <text x={plotRight + 16} y={24} className="fill-ink-muted-light" fontSize="11" fontWeight="600">
        {measure} [95% CI]
      </text>

      {/* Reference line at no effect (1.0) */}
      <line x1={x(1)} y1={top - 8} x2={x(1)} y2={top + rows.length * rowH + 8}
        stroke="currentColor" className="text-hairline-light" strokeWidth="1" />

      {/* Axis ticks */}
      {ticks.map((t) => (
        <text key={t} x={x(t)} y={top + rows.length * rowH + 24} fontSize="10"
          textAnchor="middle" className="fill-ink-muted-light">
          {t}
        </text>
      ))}

      {/* Study rows */}
      {rows.map((r, i) => {
        const y = top + i * rowH + rowH / 2;
        const side = Math.max(4, Math.min(14, r.weight)); // square sized by weight
        const isNew = highlighted.has(r.study_id);
        const mark = isNew ? "fill-accent" : "fill-ink-light";
        return (
          <g key={r.study_id}>
            <text
              x={16}
              y={y + 3}
              fontSize="11"
              className={isNew ? "fill-accent" : "fill-ink-light"}
              fontWeight={isNew ? "600" : "400"}
            >
              {r.study_id}
            </text>
            {isNew && (
              <g>
                <rect x={112} y={y - 8} width={26} height={12} rx={2} className="fill-accent" />
                <text x={125} y={y + 1} fontSize="8" textAnchor="middle" fontWeight="700" className="fill-white">
                  New
                </text>
              </g>
            )}
            <line x1={x(r.ci_low)} y1={y} x2={x(r.ci_high)} y2={y}
              stroke="currentColor" className={isNew ? "text-accent" : "text-ink-light"} strokeWidth={isNew ? "1.5" : "1"} />
            <rect x={x(r.effect) - side / 2} y={y - side / 2} width={side} height={side}
              className={mark} />
            <text x={plotRight + 16} y={y + 3} fontSize="11" className={isNew ? "fill-accent" : "fill-ink-light"}>
              {r.effect.toFixed(2)} [{r.ci_low.toFixed(2)}, {r.ci_high.toFixed(2)}]
            </text>
          </g>
        );
      })}

      {/* Pooled diamond */}
      {(() => {
        const y = top + rows.length * rowH + 40;
        const l = x(pool.ci_low);
        const c = x(pool.estimate);
        const rgt = x(pool.ci_high);
        return (
          <g>
            <polygon points={`${l},${y} ${c},${y - 8} ${rgt},${y} ${c},${y + 8}`}
              className="fill-accent" />
            <text x={16} y={y + 3} fontSize="11" fontWeight="700" className="fill-ink-light">
              Pooled (RE)
            </text>
            <text x={plotRight + 16} y={y + 3} fontSize="11" fontWeight="700" className="fill-ink-light">
              {pool.estimate.toFixed(2)} [{pool.ci_low.toFixed(2)}, {pool.ci_high.toFixed(2)}]
            </text>
          </g>
        );
      })()}
    </svg>
  );
}
