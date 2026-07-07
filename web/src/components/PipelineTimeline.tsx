import type { PipelineEvent } from "../lib/types";

const STAGE_LABEL: Record<string, string> = {
  parse: "Parse question (PICO)",
  retrieve: "Retrieve trials",
  extract: "Extract effect",
  validate: "Validate",
  pool: "Pool",
  done: "Complete",
};

export function PipelineTimeline({ events }: { events: PipelineEvent[] }) {
  return (
    <ol className="flex flex-col gap-px">
      {events.map((e, i) => (
        <li
          key={i}
          className="flex items-start gap-3 border-b border-hairline-light py-2 last:border-0"
        >
          <span className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted-light w-28 shrink-0">
            {STAGE_LABEL[e.stage] ?? e.stage}
          </span>
          <span className="font-mono text-[13px] leading-[18px] text-ink-light">
            {e.message}
          </span>
        </li>
      ))}
    </ol>
  );
}
