import type { EggerResult, PoolResult } from "../lib/types";
import { isRatioMeasure } from "../lib/types";

// Funnel plot: each study's effect (x) against its standard error (y, inverted so
// the most precise studies sit at the top). The dashed triangle is the pseudo-95%
// confidence funnel around the pooled estimate; symmetric scatter argues against
// small-study effects / publication bias. Ratio measures use a log x-axis.
export function FunnelPlot({
  pool,
  egger,
}: {
  pool: PoolResult;
  egger?: EggerResult | null;
}) {
  const ratio = isRatioMeasure(pool.measure);
  const project = ratio ? Math.log : (v: number) => v;

  const points = pool.studies.map((s) => ({
    id: s.study_id,
    effect: s.effect,
    se: Math.sqrt(s.vi),
  }));
  const center = project(pool.estimate);
  const maxSe = Math.max(...points.map((p) => p.se), pool.se_log, 0.001);

  // Half-width of the funnel at the widest (bottom) row drives the x-range.
  const halfWidth = 1.96 * maxSe;
  const spanLeft = center - halfWidth * 1.25;
  const spanRight = center + halfWidth * 1.25;

  const width = 480;
  const height = 300;
  const padL = 20;
  const padR = 20;
  const padT = 30;
  const padB = 40;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const x = (effectProjected: number) =>
    padL + ((effectProjected - spanLeft) / (spanRight - spanLeft)) * plotW;
  const y = (se: number) => padT + (se / maxSe) * plotH; // se=0 at top

  const apexX = x(center);
  const apexY = y(0);
  const leftX = x(center - 1.96 * maxSe);
  const rightX = x(center + 1.96 * maxSe);
  const baseY = y(maxSe);

  const ticks = ratio
    ? [pool.estimate / 2, pool.estimate, pool.estimate * 2]
    : [pool.estimate - halfWidth, pool.estimate, pool.estimate + halfWidth];

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full font-mono"
        role="img"
        aria-label="Funnel plot"
      >
        {/* Pseudo-95% confidence funnel */}
        <polygon
          points={`${apexX},${apexY} ${leftX},${baseY} ${rightX},${baseY}`}
          className="fill-surface-container-low"
          stroke="currentColor"
          strokeDasharray="3 3"
          strokeWidth="1"
          style={{ color: "var(--color-hairline-light, #ccc)" }}
        />
        {/* Pooled-estimate reference line */}
        <line
          x1={apexX}
          y1={apexY}
          x2={apexX}
          y2={baseY}
          stroke="currentColor"
          className="text-accent"
          strokeWidth="1"
        />
        {/* Study points */}
        {points.map((p) => (
          <circle
            key={p.id}
            cx={x(project(p.effect))}
            cy={y(p.se)}
            r={4}
            className="fill-ink-light"
            opacity={0.75}
          />
        ))}
        {/* x-axis ticks */}
        {ticks.map((t, i) => (
          <text
            key={i}
            x={x(project(t))}
            y={height - 20}
            fontSize="10"
            textAnchor="middle"
            className="fill-ink-muted-light"
          >
            {t.toFixed(2)}
          </text>
        ))}
        <text x={padL} y={padT - 12} fontSize="10" className="fill-ink-muted-light">
          SE ↓
        </text>
        <text
          x={width - padR}
          y={height - 6}
          fontSize="10"
          textAnchor="end"
          className="fill-ink-muted-light"
        >
          {pool.measure} →
        </text>
      </svg>
      {egger && egger.applicable && (
        <p className="mt-2 font-mono text-[12px] text-ink-muted-light">
          Egger's test ({egger.k} studies): intercept {egger.intercept?.toFixed(2)}, p ={" "}
          {egger.p?.toFixed(3)} —{" "}
          {egger.p != null && egger.p < 0.1
            ? "funnel asymmetry suggests possible small-study effects."
            : "no significant asymmetry."}
        </p>
      )}
    </div>
  );
}
