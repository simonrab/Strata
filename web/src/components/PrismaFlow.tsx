import type { PrismaFlow } from "../lib/types";

// A PRISMA 2020 record-flow diagram: how records moved from the search down to
// the studies pooled, with the reason for every exclusion. The counts come
// straight from the backend builder (livemeta.core.prisma), which reconciles the
// funnel — so this component only lays them out, it never computes.

function sourceLine(bySource: Record<string, number>): string {
  const parts = Object.entries(bySource)
    .filter(([, n]) => n > 0)
    .map(([src, n]) => `${n} ${src}`);
  return parts.join(" · ");
}

// A central node on the spine. `emphasis` marks the terminal synthesis box.
function StageBox({
  n,
  label,
  sub,
  emphasis,
}: {
  n: number;
  label: string;
  sub?: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={`rounded-md p-4 ${
        emphasis ? "border-2 border-accent bg-accent/5" : "hairline bg-surface-container-low"
      }`}
    >
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-2xl leading-none text-ink-light">{n}</span>
        <span className="text-[13px] font-medium text-ink-light">{label}</span>
      </div>
      {sub && <p className="mt-1.5 font-mono text-[11px] text-ink-muted-light">{sub}</p>}
    </div>
  );
}

// A branch to the right: records removed at this stage (dedup, not retrieved, or
// eligibility exclusions with their reasons).
function RemovedCard({
  title,
  n,
  reasons,
}: {
  title: string;
  n: number;
  reasons?: { reason: string; count: number }[];
}) {
  return (
    <div className="rounded-md hairline bg-card-light p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-label-caps uppercase text-ink-muted-light">{title}</span>
        <span className="font-mono text-[13px] text-risk-high">− {n}</span>
      </div>
      {reasons && reasons.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {reasons.map((r) => (
            <li
              key={r.reason}
              className="flex items-start justify-between gap-2 font-mono text-[11px] text-ink-muted-light"
            >
              <span className="flex items-start gap-1.5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-risk-high" />
                {r.reason}
              </span>
              <span className="shrink-0 text-ink-light">{r.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// One row of the spine: a central box, optionally with a removed-branch to the
// right. The down-arrow that follows sits under the central column only.
function Stage({ box, removed }: { box: React.ReactNode; removed?: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]">
      <div>{box}</div>
      <div>{removed}</div>
    </div>
  );
}

function DownArrow() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,15rem)]">
      <div className="flex justify-center py-1 text-ink-muted-light" aria-hidden>
        ↓
      </div>
    </div>
  );
}

export function PrismaFlowView({ flow }: { flow: PrismaFlow }) {
  const src = sourceLine(flow.identified_by_source);
  return (
    <section className="rounded-md hairline bg-card-light p-6" aria-label="PRISMA flow">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[13px] font-medium text-ink-light">PRISMA flow</h2>
        <span className="font-mono text-[11px] text-ink-muted-light">
          {flow.included_in_synthesis} of {flow.identified} records pooled
        </span>
      </div>
      <p className="mb-5 text-[12px] text-ink-muted-light">
        How records moved from the search to the synthesis — every exclusion accounted for.
      </p>

      <div className="flex flex-col">
        <Stage
          box={
            <StageBox
              n={flow.identified}
              label="Records identified"
              sub={src || undefined}
            />
          }
          removed={
            flow.duplicates_removed > 0 ? (
              <RemovedCard title="Duplicates removed" n={flow.duplicates_removed} />
            ) : undefined
          }
        />
        <DownArrow />

        <Stage
          box={<StageBox n={flow.screened} label="Records screened" />}
          removed={
            flow.not_retrieved > 0 ? (
              <RemovedCard title="Reports not retrieved" n={flow.not_retrieved} />
            ) : undefined
          }
        />
        <DownArrow />

        <Stage
          box={<StageBox n={flow.assessed} label="Reports assessed for eligibility" />}
          removed={
            flow.excluded.length > 0 ? (
              <RemovedCard
                title="Records excluded"
                n={flow.excluded.reduce((s, e) => s + e.count, 0)}
                reasons={flow.excluded.map((e) => ({ reason: e.reason, count: e.count }))}
              />
            ) : undefined
          }
        />
        <DownArrow />

        <Stage box={<StageBox n={flow.included} label="Studies included in review" />} />
        <DownArrow />

        <Stage
          box={
            <StageBox
              n={flow.included_in_synthesis}
              label="Studies included in synthesis (meta-analysis)"
              sub={flow.synthesis_note || undefined}
              emphasis
            />
          }
        />
      </div>
    </section>
  );
}
