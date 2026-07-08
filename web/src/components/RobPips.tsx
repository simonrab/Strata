import type { RobAssessment, RobJudgment } from "../lib/types";

// Risk-of-bias pip bar. When a RoB 2 assessment is available, each of the five
// pips is coloured by its domain judgment; otherwise the bar shows the grey
// "pending / not assessed" placeholder.
const PIP_COLOR: Record<RobJudgment, string> = {
  low: "bg-risk-low",
  some_concerns: "bg-risk-some",
  high: "bg-error",
  pending: "bg-outline-variant",
};

const OVERALL_LABEL: Record<RobJudgment, string> = {
  low: "Low",
  some_concerns: "Some",
  high: "High",
  pending: "Pending",
};

export function RobPips({
  pending,
  assessment,
}: {
  pending: boolean;
  assessment?: RobAssessment;
}) {
  const judgments: RobJudgment[] = assessment
    ? assessment.domains.map((d) => d.judgment)
    : Array.from({ length: 5 }, () => "pending" as RobJudgment);
  const overall = assessment?.overall ?? (pending ? "pending" : "pending");

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[10px] font-semibold uppercase tracking-wider text-ink-muted-light md:inline">
        {OVERALL_LABEL[overall]}
      </span>
      <div
        className={`flex gap-[2px] rounded-sm hairline bg-white p-[2px] ${
          overall === "pending" ? "opacity-50" : ""
        }`}
        aria-label={`risk of bias ${OVERALL_LABEL[overall].toLowerCase()}`}
      >
        {judgments.map((j, i) => (
          <span key={i} className={`h-3 w-1.5 rounded-[1px] ${PIP_COLOR[j]}`} />
        ))}
      </div>
    </div>
  );
}
