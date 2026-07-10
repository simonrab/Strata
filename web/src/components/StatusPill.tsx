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

// Bordered chips (no filled/tinted background): a hairline in the semantic
// colour, coloured text, and a solid icon. Reads as precise, not decorative.
const config: Record<TrialStatus, { label: string; icon: string; tone: string }> = {
  pooled: { label: "Pooled", icon: "check_circle", tone: "border-accent text-accent" },
  confirmed: { label: "Confirmed", icon: "verified", tone: "border-risk-low text-risk-low" },
  review: { label: "Review", icon: "pending", tone: "border-risk-some text-risk-some" },
};

export function StatusPill({ status }: { status: TrialStatus }) {
  const c = config[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border bg-card-light px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${c.tone}`}
    >
      <Icon name={c.icon} size={13} fill />
      <span>{c.label}</span>
    </span>
  );
}
