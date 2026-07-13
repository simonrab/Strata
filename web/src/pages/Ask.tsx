import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useReview } from "../lib/review";
import { ApiError, parseQuestion } from "../lib/api";
import { Icon } from "../components/Icon";
import { SourceToggle, loadSources } from "../components/SourceToggle";
import type { Question, Source } from "../lib/types";

const PICO_FIELDS = [
  ["population", "Population"],
  ["intervention", "Intervention"],
  ["comparator", "Comparator"],
  ["outcome", "Outcome"],
] as const;

// Effect measures the pipeline can pool end to end. Claude picks one when
// parsing; the user can override before running (e.g. a continuous outcome).
const MEASURES = [
  ["HR", "Hazard ratio (time-to-event)"],
  ["RR", "Risk ratio (binary)"],
  ["OR", "Odds ratio (binary)"],
  ["MD", "Mean difference (continuous)"],
  ["SMD", "Std. mean difference (continuous)"],
] as const;

export function Ask() {
  const { start } = useReview();
  const navigate = useNavigate();

  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Question | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>(loadSources());

  const parse = async () => {
    setParsing(true);
    setError(null);
    try {
      setParsed(await parseQuestion(text));
    } catch (err) {
      setParsed(null);
      if (
        err instanceof ApiError &&
        (err.code === "llm_credits_exhausted" || err.status === 402)
      ) {
        setError(
          "Strata is out of Claude API credits, so the question can't be parsed right now. Top up the Anthropic account, then try again."
        );
      } else {
        setError("Could not parse the question. Is the backend running on :8000?");
      }
    } finally {
      setParsing(false);
    }
  };

  const editPico = (field: string, value: string) => {
    if (!parsed) return;
    setParsed({ ...parsed, pico: { ...parsed.pico, [field]: value } });
  };

  const run = () => {
    if (!parsed) return;
    start(parsed, sources);
    navigate("/run");
  };

  return (
    <div
      className={`mx-auto flex max-w-2xl flex-col items-center px-6 text-center ${
        parsed ? "pt-16 pb-20" : "min-h-[82vh] justify-center pb-16"
      }`}
    >
      <p className="text-label-caps uppercase text-ink-muted-light">
        Living evidence review
      </p>
      <h1 className="mt-3 font-sans text-display-lg text-ink-light">
        What question should we synthesize evidence for?
      </h1>

      {/* Chat-style prompt: a single prominent, centered input with an inline send. */}
      <div className="mt-8 w-full">
        <div className="relative rounded-2xl hairline bg-card-light shadow-sm transition-colors focus-within:border-accent">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) parse();
            }}
            rows={4}
            aria-label="Clinical question"
            placeholder="Ask a clinical question in PICO form — population, intervention, comparator, and one outcome."
            className="max-h-64 w-full resize-none overflow-y-auto rounded-2xl bg-transparent p-4 pr-14 text-left text-[16px] leading-7 text-ink-light outline-none placeholder:text-ink-muted-light"
          />
          <button
            onClick={parse}
            disabled={!text.trim() || parsing}
            aria-label="Parse into PICO"
            title="Parse into PICO (⌘↵)"
            className="absolute bottom-3 right-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Icon name={parsing ? "more_horiz" : "arrow_upward"} size={18} />
          </button>
        </div>
        <p className="mt-3 text-[12px] text-ink-muted-light">
          Structured as PICO into a living meta-analysis of published trials — a
          research tool, not medical advice.
        </p>
        {error && (
          <div
            role="alert"
            className="mt-3 flex items-start gap-2 rounded-md border border-risk-high/40 bg-risk-high-container px-3 py-2.5 text-left"
          >
            <Icon name="error" size={16} className="mt-0.5 shrink-0 text-risk-high" />
            <p className="text-[13px] leading-5 text-risk-high">{error}</p>
          </div>
        )}
      </div>

      {parsed && (
        <div className="mt-10 w-full rounded-md hairline bg-card-light p-6 text-left">
          <p className="text-label-caps uppercase text-ink-muted-light">
            Parsed PICO · edit any field before running
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-4">
            {PICO_FIELDS.map(([key, label]) => (
              <div key={key}>
                <dt className="text-label-caps uppercase text-ink-muted-light">
                  {label}
                </dt>
                <input
                  value={parsed.pico[key]}
                  onChange={(e) => editPico(key, e.target.value)}
                  aria-label={label}
                  className="mt-1 w-full rounded-sm hairline bg-surface-container-low px-2 py-1 text-[14px] text-ink-light outline-none focus:border-accent"
                />
              </div>
            ))}
          </dl>

          <div className="mt-6 flex flex-wrap items-center gap-4 hairline-t pt-4">
            <span className="font-mono text-[13px] text-ink-muted-light">
              {parsed.trial_ids.length > 0
                ? `${parsed.trial_ids.length} candidate trials · pooling`
                : "trials discovered from ClinicalTrials.gov on run"}
            </span>
            <label className="sr-only" htmlFor="measure-select">
              Effect measure
            </label>
            <select
              id="measure-select"
              aria-label="Effect measure"
              value={parsed.measure}
              onChange={(e) => setParsed({ ...parsed, measure: e.target.value })}
              className="rounded-sm hairline bg-surface-container-low px-2 py-1 text-[13px] text-ink-light outline-none focus:border-accent"
            >
              {MEASURES.map(([value, label]) => (
                <option key={value} value={value}>
                  {value} · {label}
                </option>
              ))}
            </select>
            <SourceToggle value={sources} onChange={setSources} />
            <button
              onClick={run}
              className="ml-auto inline-flex items-center gap-1.5 rounded-sm bg-ink-light px-5 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
            >
              <Icon name="play_arrow" size={18} fill />
              Run review
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
