import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview } from "../lib/api";
import { Icon } from "../components/Icon";
import type { ReviewResult, ValidationResult } from "../lib/types";
import { StatusPill, trialStatus } from "../components/StatusPill";
import { RobPips } from "../components/RobPips";
import { ProvenancePopover } from "../components/ProvenancePopover";

function Prisma({ review }: { review: ReviewResult }) {
  const identified = review.question.trial_ids.length;
  const screened = review.extractions.length;
  const assessed = review.validations.filter((v) => v.passed).length;
  const pooled = review.pool?.k ?? 0;
  const steps: [number, string, boolean][] = [
    [identified, "Identified", false],
    [screened, "Screened", false],
    [assessed, "Assessed", false],
    [pooled, "Pooled", true],
  ];
  return (
    <section className="overflow-x-auto rounded-md hairline bg-card-light p-4">
      <div className="flex min-w-max items-center gap-3">
        <span className="w-16 text-right text-label-caps uppercase text-ink-muted-light">
          PRISMA
        </span>
        <div className="mx-2 h-4 w-px bg-hairline-light" />
        {steps.map(([n, label, hl], i) => (
          <div key={label} className="flex items-center gap-3">
            <div className="flex flex-col items-center">
              <span
                className={`font-mono text-[13px] ${hl ? "font-bold text-accent" : "text-ink-light"}`}
              >
                {n}
              </span>
              <span
                className={`mt-1 text-[10px] font-semibold uppercase tracking-wider ${
                  hl ? "text-accent" : "text-ink-muted-light"
                }`}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <Icon name="arrow_forward" size={18} className="text-outline-variant" />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export function EvidenceLedger() {
  const { id = "" } = useParams();
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getReview(id)
      .then(setReview)
      .catch(() => setError(true));
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">No such review.</p>
      </div>
    );
  }
  if (!review) {
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading evidence…</p>
      </div>
    );
  }

  const byStudy = new Map<string, ValidationResult>(
    review.validations.map((v) => [v.study_id, v])
  );
  const robByStudy = new Map(review.rob.map((a) => [a.study_id, a]));

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-10">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-sans text-display-lg text-ink-light">
            Evidence Ledger
          </h1>
          <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
            {review.question.pico.intervention} vs {review.question.pico.comparator} —{" "}
            {review.question.pico.outcome}
          </p>
        </div>
        <Link
          to={`/reviews/${id}/report`}
          className="rounded-sm hairline px-4 py-2 text-[13px] font-medium text-ink-light hover:bg-surface-container-high"
        >
          View report →
        </Link>
      </div>

      <Prisma review={review} />

      <section className="overflow-x-auto rounded-md hairline bg-card-light">
        <div className="grid min-w-[720px] grid-cols-12 gap-3 hairline-b bg-surface-container-low p-3 text-label-caps uppercase text-ink-muted-light">
          <div className="col-span-4">Trial</div>
          <div className="col-span-3">Effect (HR [95% CI])</div>
          <div className="col-span-2 text-center">Status</div>
          <div className="col-span-3 text-right">Risk of Bias</div>
        </div>

        {review.extractions.map((e) => {
          const status = trialStatus(e, byStudy.get(e.study_id));
          const pending = status === "review";
          return (
            <div
              key={e.study_id}
              className="grid min-w-[720px] grid-cols-12 items-center gap-3 hairline-b p-3 last:border-0 hover:bg-surface-container-low"
            >
              <div className="col-span-4 min-w-0">
                <Link
                  to={`/reviews/${id}/evidence/${e.study_id}`}
                  className="block truncate text-[14px] text-ink-light hover:text-accent"
                >
                  {e.label}
                </Link>
                <span className="font-mono text-[11px] text-ink-muted-light">{e.study_id}</span>
              </div>
              <div className="col-span-3 flex items-center gap-2">
                {e.hr != null ? (
                  <>
                    <span className="rounded-sm hairline bg-surface-container px-1.5 py-0.5 font-mono text-[13px] text-ink-light">
                      {e.hr.toFixed(2)} [{e.ci_low?.toFixed(2)}, {e.ci_high?.toFixed(2)}]
                    </span>
                    <ProvenancePopover provenance={e.provenance} />
                  </>
                ) : (
                  <span className="font-mono text-[11px] italic text-outline">
                    {e.flag_reason ?? "Not extracted"}
                  </span>
                )}
              </div>
              <div className="col-span-2 flex justify-center">
                <StatusPill status={status} />
              </div>
              <div className="col-span-3 flex justify-end">
                <RobPips pending={pending} assessment={robByStudy.get(e.study_id)} />
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
