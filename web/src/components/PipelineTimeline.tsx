import type { PipelineEvent } from "../lib/types";
import { Icon } from "./Icon";

const STAGE_ORDER = [
  "parse",
  "retrieve",
  "extract",
  "validate",
  "pool",
  "appraise",
  "sensitivity",
  "grade",
  "done",
];

const STEPS = [
  { label: "Searching", stages: ["parse", "retrieve"] },
  { label: "Extracting", stages: ["extract"] },
  { label: "Validating", stages: ["validate"] },
  { label: "Pooling", stages: ["pool"] },
  { label: "Risk of bias", stages: ["appraise", "sensitivity"] },
  { label: "Grading", stages: ["grade", "done"] },
];

type StepState = "done" | "active" | "pending";

// The execution stepper: maps the streamed PipelineEvent stages onto six
// user-facing steps and shows each as done / active / pending.
export function PipelineTimeline({
  events,
  done = false,
}: {
  events: PipelineEvent[];
  done?: boolean;
}) {
  const furthest = events.reduce((m, e) => Math.max(m, STAGE_ORDER.indexOf(e.stage)), -1);

  function stateOf(stages: string[]): StepState {
    const idxs = stages.map((s) => STAGE_ORDER.indexOf(s));
    const first = Math.min(...idxs);
    const last = Math.max(...idxs);
    if (done || furthest > last) return "done";
    if (furthest >= first) return "active";
    return "pending";
  }

  return (
    <ol className="space-y-1">
      {STEPS.map((step) => {
        const s = stateOf(step.stages);
        return (
          <li key={step.label} className="flex items-center gap-3 py-1.5">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full ${
                s === "done"
                  ? "bg-risk-low-container text-risk-low"
                  : s === "active"
                  ? "bg-accent-container text-accent"
                  : "bg-surface-container text-outline-variant"
              }`}
            >
              {s === "done" ? (
                <Icon name="check_circle" size={18} fill />
              ) : s === "active" ? (
                <Icon name="sync" size={18} className="animate-spin" />
              ) : (
                <Icon name="radio_button_unchecked" size={18} />
              )}
            </span>
            <span
              className={`text-[13px] ${
                s === "pending" ? "text-ink-muted-light" : "text-ink-light"
              } ${s === "active" ? "font-medium" : ""}`}
            >
              {step.label}
            </span>
            <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-ink-muted-light">
              {s === "done" ? "done" : s === "active" ? "running" : ""}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
