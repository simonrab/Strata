import { Icon } from "./Icon";
import type { TrialExtraction, ValidationResult } from "../lib/types";

export type TrialStatus = "pooled" | "review" | "confirmed";

export function trialStatus(
  ext: TrialExtraction,
  validation?: ValidationResult
): TrialStatus {
  if (ext.flagged || (validation && !validation.passed)) return "review";
  if (ext.confirmed) return "confirmed";
  return "pooled";
}

const config: Record<TrialStatus, { label: string; icon: string; box: string }> = {
  pooled: { label: "Pooled", icon: "check_circle", box: "bg-accent-container text-accent" },
  confirmed: {
    label: "Confirmed",
    icon: "verified",
    box: "bg-risk-low-container text-risk-low",
  },
  review: { label: "Review", icon: "pending", box: "bg-risk-some-container text-risk-some" },
};

export function StatusPill({ status }: { status: TrialStatus }) {
  const c = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${c.box}`}
    >
      <Icon name={c.icon} size={13} fill />
      <span>{c.label}</span>
    </span>
  );
}
