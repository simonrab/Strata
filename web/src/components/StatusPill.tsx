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

const styles: Record<TrialStatus, string> = {
  pooled: "bg-[#e0f2fe] text-[#0369a1] border-[#bae6fd]",
  confirmed: "bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]",
  review: "bg-[#fef3c7] text-[#b45309] border-[#fde68a]",
};

const labels: Record<TrialStatus, string> = {
  pooled: "Pooled",
  confirmed: "Confirmed",
  review: "Review",
};

export function StatusPill({ status }: { status: TrialStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}
