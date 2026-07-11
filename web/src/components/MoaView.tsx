import { Link } from "react-router-dom";
import type { MoaCluster, MoaLandscape } from "../lib/types";
import { PHASE_LABEL, type Phase } from "../lib/types";
import { Icon } from "./Icon";

// Mechanism-of-action clusters. Each card is one drug class with a phase
// distribution, its assets, and class-level evidence (plain language leading).

const PHASE_ORDER: Phase[] = [
  "preclinical", "phase_1", "phase_1_2", "phase_2", "phase_2_3",
  "phase_3", "phase_4", "filed", "approved", "withdrawn", "unknown",
];

// Muted → accent → green, matching the StagePill gradient.
const BAR_TONE: Record<Phase, string> = {
  preclinical: "bg-surface-container-high",
  phase_1: "bg-surface-container-high",
  phase_1_2: "bg-accent-container",
  phase_2: "bg-accent-container",
  phase_2_3: "bg-accent-container",
  phase_3: "bg-accent",
  phase_4: "bg-accent",
  filed: "bg-risk-some",
  approved: "bg-risk-low",
  withdrawn: "bg-risk-high",
  unknown: "bg-surface-container",
};

function StageBar({ dist }: { dist: Record<string, number> }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
  const segments = PHASE_ORDER.filter((p) => dist[p]);
  return (
    <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-sm" role="img" aria-label="stage distribution">
      {segments.map((p) => (
        <span
          key={p}
          className={`${BAR_TONE[p]} rounded-sm`}
          style={{ width: `${(dist[p] / total) * 100}%` }}
          title={`${PHASE_LABEL[p]}: ${dist[p]}`}
        />
      ))}
    </div>
  );
}

function ClusterCard({ cluster }: { cluster: MoaCluster }) {
  const unclassified = cluster.drug_class === "unclassified";
  return (
    <div className="rounded-md hairline bg-card-light p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[15px] font-medium text-ink-light">{cluster.label}</h3>
        <span className="font-mono text-[11px] text-ink-muted-light">
          {cluster.assets.length} asset{cluster.assets.length === 1 ? "" : "s"} ·{" "}
          {cluster.program_count} program{cluster.program_count === 1 ? "" : "s"}
        </span>
      </div>

      {!unclassified && (
        <div className="my-3 flex items-center gap-2">
          <span className="w-16 text-[11px] text-ink-muted-light">stage</span>
          <div className="flex-1">
            <StageBar dist={cluster.stage_distribution} />
          </div>
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {cluster.assets.slice(0, 6).map((a) => (
            <Link
              key={a}
              to={`/asset/${encodeURIComponent(a)}`}
              className="rounded-full hairline bg-surface-container-low px-2.5 py-0.5 text-[11px] text-ink-muted-light hover:text-ink-light"
            >
              {a}
            </Link>
          ))}
          {cluster.assets.length > 6 && (
            <span className="px-1 text-[11px] text-ink-muted-light">
              +{cluster.assets.length - 6}
            </span>
          )}
        </div>
        {unclassified && (
          <span className="inline-flex items-center gap-1 text-[11px] text-ink-muted-light">
            <Icon name="help" size={12} /> class not inferred with confidence
          </span>
        )}
      </div>
    </div>
  );
}

export function MoaView({ moa }: { moa: MoaLandscape }) {
  if (moa.clusters.length === 0) {
    return (
      <div className="rounded-md hairline bg-card-light p-8 text-center text-[14px] text-ink-muted-light">
        No assets to cluster for <span className="font-medium">{moa.condition}</span>.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {moa.clusters.map((c) => (
        <ClusterCard key={c.drug_class} cluster={c} />
      ))}
    </div>
  );
}
