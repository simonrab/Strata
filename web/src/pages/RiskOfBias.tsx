import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview, postRobDecision } from "../lib/api";
import type { RobAssessment, RobJudgment, ReviewResult } from "../lib/types";

const JUDGMENT: Record<
  RobJudgment,
  { label: string; symbol: string; box: string; text: string }
> = {
  low: { label: "Low risk", symbol: "+", box: "bg-risk-low-container", text: "text-risk-low" },
  some_concerns: {
    label: "Some concerns",
    symbol: "?",
    box: "bg-risk-some-container",
    text: "text-risk-some",
  },
  high: { label: "High risk", symbol: "−", box: "bg-risk-high", text: "text-white" },
  pending: {
    label: "Not assessed",
    symbol: "·",
    box: "bg-surface-container-high",
    text: "text-ink-muted-light",
  },
};

function Dot({ judgment }: { judgment: RobJudgment }) {
  const j = JUDGMENT[judgment];
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex h-6 w-6 items-center justify-center rounded-sm font-mono text-[13px] font-bold ${j.box} ${j.text}`}
      >
        {j.symbol}
      </span>
      <span className="text-[13px] text-ink-light">{j.label}</span>
    </div>
  );
}

export function RiskOfBias() {
  const { id = "" } = useParams();
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState(0);
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    getReview(id)
      .then(setReview)
      .catch(() => setError(true));
  }, [id]);

  if (error)
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-risk-high">No such review.</p>
      </div>
    );
  if (!review)
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">Loading appraisal…</p>
      </div>
    );

  const assessments = review.rob;
  const active: RobAssessment | undefined = assessments[selected];
  const pending = active?.overall === "pending";

  async function verify(domainKey: string) {
    if (!active) return;
    setSaving(domainKey);
    try {
      const updated = await postRobDecision(id, {
        study_id: active.study_id,
        domain_key: domainKey,
      });
      setReview(updated);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-8 py-10">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <p className="text-label-caps uppercase text-outline">
            Domain assessment
          </p>
          <h1 className="mt-1 font-sans text-display-lg text-ink-light">
            Risk of Bias (RoB 2)
          </h1>
          <p className="mt-1 flex items-center gap-2 text-[14px] text-ink-muted-light">
            RoB 2 domains judged from the trial record; a reviewer confirms each.
          </p>
        </div>
        {active && (
          <div className="rounded-sm hairline bg-card-light px-4 py-2">
            <p className="text-label-caps uppercase text-outline">
              Overall judgment
            </p>
            <div className="mt-1">
              <Dot judgment={active.overall} />
            </div>
          </div>
        )}
      </div>

      {assessments.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {assessments.map((a, i) => (
            <button
              key={a.study_id}
              onClick={() => setSelected(i)}
              className={`rounded-sm border px-3 py-1.5 text-[12px] font-medium transition-colors ${
                i === selected
                  ? "border-accent bg-surface-container-high text-accent"
                  : "border-hairline-light text-ink-muted-light hover:bg-surface-container-low"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}

      {pending && (
        <p className="rounded-sm hairline bg-surface-container-low px-4 py-3 font-mono text-[12px] text-ink-muted-light">
          Not yet assessed — risk-of-bias judgments require the model
          (ANTHROPIC_API_KEY not configured). We abstain rather than fabricate a
          judgment.
        </p>
      )}

      {active && (
        <section className="overflow-x-auto rounded-md hairline bg-card-light">
          <div className="grid min-w-[820px] grid-cols-12 gap-3 hairline-b bg-surface-container-low p-3 text-label-caps uppercase text-ink-muted-light">
            <div className="col-span-2">Domain</div>
            <div className="col-span-2">Judgment</div>
            <div className="col-span-4">Rationale</div>
            <div className="col-span-3">Source quote</div>
            <div className="col-span-1 text-right">Action</div>
          </div>
          {active.domains.map((d) => (
            <div
              key={d.key}
              className="grid min-w-[820px] grid-cols-12 items-start gap-3 hairline-b p-3 last:border-0 hover:bg-surface-container-low"
            >
              <div className="col-span-2">
                <p className="text-[14px] text-ink-light">
                  {d.key}: {d.name.split(" ")[0]}
                </p>
                <p className="font-mono text-[11px] text-ink-muted-light">{d.name}</p>
              </div>
              <div className="col-span-2">
                <Dot judgment={d.judgment} />
              </div>
              <div className="col-span-4 text-[13px] text-ink-light">
                {d.rationale || <span className="text-ink-muted-light">—</span>}
              </div>
              <div className="col-span-3 border-l-2 border-hairline-light pl-3 font-serif text-[13px] italic text-ink-muted-light">
                {d.source_quote?.snippet ? `"${d.source_quote.snippet}"` : "—"}
              </div>
              <div className="col-span-1 flex justify-end">
                {d.confirmed ? (
                  <span className="inline-flex items-center rounded-full bg-risk-low-container px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-risk-low">
                    Verified
                  </span>
                ) : (
                  <button
                    onClick={() => verify(d.key)}
                    disabled={pending || saving === d.key}
                    className="rounded-sm hairline px-3 py-1 text-label-caps uppercase text-ink-light hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {saving === d.key ? "…" : "Verify"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      <Link
        to={`/reviews/${id}/grade`}
        className="inline-block text-label-caps uppercase text-ink-muted-light hover:text-accent"
      >
        GRADE certainty →
      </Link>
    </div>
  );
}
