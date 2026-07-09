import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useReview } from "../lib/review";
import { parseQuestion } from "../lib/api";
import { Icon } from "../components/Icon";
import type { Question } from "../lib/types";

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
  const { question, start } = useReview();
  const navigate = useNavigate();

  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Question | null>(null);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Seed the box with the demo question *once* so the demo is one click away —
  // but never re-seed, or clearing the box to type a fresh question would snap
  // straight back to the demo text.
  const seeded = useRef(false);
  useEffect(() => {
    if (question && !seeded.current) {
      setText(question.text);
      seeded.current = true;
    }
  }, [question]);

  const parse = async () => {
    setParsing(true);
    setError(null);
    try {
      setParsed(await parseQuestion(text));
    } catch {
      setError("Could not parse the question. Is the backend running on :8000?");
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
    start(parsed);
    navigate("/run");
  };

  return (
    <div className="mx-auto max-w-3xl px-8 py-10">
      <p className="text-label-caps uppercase text-ink-muted-light">
        New living review
      </p>
      <h1 className="mt-2 font-sans text-display-lg text-ink-light">
        Ask a clinical question
      </h1>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        aria-label="Clinical question"
        placeholder="e.g. In adults with type 2 diabetes, do GLP-1 receptor agonists reduce MACE versus placebo?"
        className="mt-6 w-full rounded-md hairline bg-card-light p-4 font-serif text-[18px] leading-7 text-ink-light outline-none focus:border-accent"
      />

      <div className="mt-3 flex items-center gap-4">
        <button
          onClick={parse}
          disabled={!text.trim() || parsing}
          className="rounded-sm hairline px-4 py-2 text-[13px] font-medium text-ink-light hover:bg-surface-container-high disabled:opacity-40"
        >
          {parsing ? "Parsing…" : "Parse into PICO"}
        </button>
        {error && <span className="font-mono text-[12px] text-risk-high">{error}</span>}
      </div>

      {parsed && (
        <div className="mt-8 rounded-md hairline bg-card-light p-6">
          <p className="text-label-caps uppercase text-ink-muted-light">
            Parsed PICO — edit any field before running
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
              {parsed.trial_ids.length} candidate trials · pooling
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
                  {value} — {label}
                </option>
              ))}
            </select>
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
