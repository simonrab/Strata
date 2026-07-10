import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReview } from "../lib/api";
import { Icon } from "../components/Icon";
import { FunnelPlot } from "../components/FunnelPlot";
import type { GradeRating, ReviewResult } from "../lib/types";

const CERTAINTY_DOTS: Record<GradeRating, number> = {
  high: 4,
  moderate: 3,
  low: 2,
  very_low: 1,
};

function CertaintyDots({ rating }: { rating: GradeRating }) {
  const filled = CERTAINTY_DOTS[rating];
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex gap-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <span
            key={i}
            className={`h-3 w-3 rounded-full ${i < filled ? "bg-accent" : "bg-surface-container-highest"}`}
          />
        ))}
      </div>
      <span className="text-label-caps uppercase text-ink-light">
        {rating.replace("_", " ")}
      </span>
    </div>
  );
}

const DOMAIN_LABEL: Record<string, string> = {
  risk_of_bias: "Risk of Bias",
  inconsistency: "Inconsistency",
  indirectness: "Indirectness",
  imprecision: "Imprecision",
  publication_bias: "Publication Bias",
};

function seriousStyle(serious: string): { box: string; label: string } {
  if (serious === "serious") return { box: "bg-risk-some", label: "Serious (−1)" };
  if (serious === "very_serious")
    return { box: "bg-error", label: "Very serious (−2)" };
  return { box: "bg-risk-low", label: "Not serious" };
}

export function GradeDetail() {
  const { id = "" } = useParams();
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [error, setError] = useState(false);

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
        <p className="font-mono text-[13px] text-ink-muted-light">Loading GRADE…</p>
      </div>
    );

  const { grade, pool, question } = review;
  if (!grade || !pool)
    return (
      <div className="mx-auto max-w-6xl px-8 py-10">
        <p className="font-mono text-[13px] text-ink-muted-light">
          No GRADE rating. The review has not been pooled.
        </p>
      </div>
    );

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-8 py-10">
      <div>
        <h1 className="font-sans text-display-lg text-ink-light">
          Summary of Findings
        </h1>
        <p className="mt-1 font-serif text-[16px] text-ink-muted-light">
          Certainty of evidence for {question.pico.outcome}.
        </p>
      </div>

      {/* Summary of Findings table */}
      <section className="overflow-x-auto rounded-md hairline bg-card-light">
        <table className="w-full min-w-[720px] border-collapse text-left">
          <thead className="hairline-b bg-surface-container-low">
            <tr className="text-label-caps uppercase text-ink-muted-light">
              <th className="p-4">Outcome</th>
              <th className="p-4">Studies</th>
              <th className="p-4 text-right">Relative effect (95% CI)</th>
              <th className="p-4 text-center">Certainty</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-4">
                <span className="block text-[14px] font-medium text-ink-light">
                  {grade.outcome}
                </span>
              </td>
              <td className="p-4 align-top font-mono text-[13px] text-ink-light">
                {pool.k} RCTs
              </td>
              <td className="p-4 text-right align-top">
                <span className="font-mono text-[14px] font-medium text-ink-light">
                  {pool.measure} {pool.estimate.toFixed(2)}
                </span>
                <br />
                <span className="font-mono text-[12px] text-ink-muted-light">
                  ({pool.ci_low.toFixed(2)} to {pool.ci_high.toFixed(2)})
                </span>
              </td>
              <td className="p-4 text-center align-top">
                <CertaintyDots rating={grade.certainty} />
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <p className="border-l-2 border-accent pl-4 font-serif text-[18px] leading-7 text-ink-light">
        {grade.sof_line}
      </p>

      {/* Certainty detail: 5-domain grid */}
      <div>
        <h2 className="mb-4 flex items-center gap-2 text-[13px] font-medium text-ink-light">
          <Icon name="analytics" size={18} className="text-accent" />
          Certainty detail · five GRADE domains
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-5">
          {grade.domains.map((d) => {
            const s = seriousStyle(d.serious);
            const downgraded = d.downgrade < 0;
            return (
              <div
                key={d.name}
                className={`relative flex h-full flex-col overflow-hidden rounded-sm border p-4 ${
                  downgraded ? "border-accent bg-surface-container-low" : "border-hairline-light bg-card-light"
                }`}
              >
                {downgraded && (
                  <span className="absolute right-0 top-0 bg-accent px-1.5 py-0.5 font-mono text-[10px] uppercase text-on-primary">
                    Downgraded
                  </span>
                )}
                <p className="mb-3 text-label-caps uppercase text-outline">
                  {DOMAIN_LABEL[d.name] ?? d.name}
                  {d.by_claude && (
                    <Icon
                      name="auto_awesome"
                      size={12}
                      className="ml-1 align-middle text-accent"
                      label="Judged by Claude"
                    />
                  )}
                </p>
                <div className="mb-3 flex items-center gap-2">
                  <span className={`h-4 w-4 rounded-sm ${s.box}`} />
                  <span className="text-[14px] font-medium text-ink-light">{s.label}</span>
                </div>
                <p className="mt-auto text-[13px] leading-relaxed text-ink-muted-light">
                  {d.rationale}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Funnel plot — quantitative publication-bias check (>= 10 studies) */}
      {grade.publication_bias_test?.applicable && pool.studies.length > 0 && (
        <div>
          <h2 className="mb-4 flex items-center gap-2 text-[13px] font-medium text-ink-light">
            <Icon name="scatter_plot" size={18} className="text-accent" />
            Funnel plot · small-study effects
          </h2>
          <div className="max-w-xl rounded-md hairline bg-card-light p-5">
            <FunnelPlot pool={pool} egger={grade.publication_bias_test} />
          </div>
        </div>
      )}

      {grade.footnotes.length > 0 && (
        <div className="max-w-4xl hairline-t pt-4">
          {grade.footnotes.map((f, i) => (
            <p key={i} className="mb-1 text-[12px] leading-relaxed text-ink-muted-light">
              <sup className="pr-1 text-accent">{String.fromCharCode(97 + i)}</sup>
              {f}
            </p>
          ))}
        </div>
      )}

      <Link
        to={`/reviews/${id}/report`}
        className="inline-block text-label-caps uppercase text-ink-muted-light hover:text-accent"
      >
        View report →
      </Link>
    </div>
  );
}
