import { Link } from "react-router-dom";
import type { EvidenceBadge } from "../lib/types";
import { Icon } from "./Icon";

// The living pooled-evidence badge on a competitive cell. Three honest states,
// so a cell never shows a fabricated number:
//   pooled     — the committed estimate + GRADE, colored by the conclusion
//   gate_open  — pooling withheld pending a homogeneity confirmation
//   abstained  — too few trials / no poolable data
export function EvidenceBadgeView({ badge }: { badge: EvidenceBadge }) {
  if (badge.state === "gate_open") {
    return (
      <div
        data-testid="evidence-gate"
        className="mt-1 flex items-center gap-1 rounded-sm border border-risk-some bg-card-light px-1.5 py-0.5 text-[10px] font-medium text-risk-some"
        title="The meta-analysis withheld its pooled estimate until a reviewer confirms these trials are similar enough to combine."
      >
        <Icon name="gpp_maybe" size={12} />
        Gate · pending confirmation
      </div>
    );
  }

  if (badge.state === "abstained") {
    return (
      <div
        data-testid="evidence-abstained"
        className="mt-1 inline-flex items-center gap-1 rounded-sm bg-surface-container px-1.5 py-0.5 text-[10px] font-medium text-outline"
      >
        <Icon name="do_not_disturb_on" size={12} />
        Evidence abstained
      </div>
    );
  }

  const significant = (badge.conclusion ?? "").startsWith("significant");
  const tone = significant
    ? "bg-risk-low-container text-risk-low"
    : "bg-surface-container-high text-ink-muted-light";
  const value =
    badge.estimate != null && badge.ci_low != null && badge.ci_high != null
      ? `${badge.measure} ${badge.estimate.toFixed(2)} [${badge.ci_low.toFixed(2)}, ${badge.ci_high.toFixed(2)}]`
      : badge.measure;

  return (
    <Link
      to={`/reviews/${encodeURIComponent(badge.question_id)}/report`}
      data-testid="evidence-pooled"
      className={`mt-1 block rounded-sm px-1.5 py-1 text-[10px] leading-tight ${tone} hover:underline`}
      title={badge.conclusion ?? undefined}
    >
      <span className="font-mono font-semibold">{value}</span>
      {badge.grade_certainty && (
        <span className="ml-1 uppercase opacity-80">· GRADE {badge.grade_certainty}</span>
      )}
    </Link>
  );
}
