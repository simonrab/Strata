import { useNavigate } from "react-router-dom";
import { useReview } from "../lib/review";

export function Ask() {
  const { question, start } = useReview();
  const navigate = useNavigate();

  const run = () => {
    start();
    navigate("/run");
  };

  return (
    <div className="mx-auto max-w-3xl px-8 py-12">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
        New living review
      </p>
      <h1 className="mt-2 font-serif text-[28px] leading-tight text-ink-light">
        Ask a clinical question
      </h1>

      {question ? (
        <div className="mt-8 rounded-md border border-hairline-light bg-card-light p-6">
          <p className="font-serif text-[18px] leading-7 text-ink-light">{question.text}</p>

          <dl className="mt-6 grid grid-cols-2 gap-x-8 gap-y-4">
            {(
              [
                ["Population", question.pico.population],
                ["Intervention", question.pico.intervention],
                ["Comparator", question.pico.comparator],
                ["Outcome", question.pico.outcome],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <dt className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
                  {k}
                </dt>
                <dd className="mt-1 text-[14px] text-ink-light">{v}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-6 flex items-center gap-4 border-t border-hairline-light pt-4">
            <span className="font-mono text-[13px] text-ink-muted-light">
              {question.trial_ids.length} candidate trials · pooling {question.measure}
            </span>
            <button
              onClick={run}
              className="ml-auto rounded-sm bg-ink-light px-5 py-2 text-[13px] font-medium text-canvas-light hover:opacity-90"
            >
              Run review
            </button>
          </div>
        </div>
      ) : (
        <p className="mt-8 font-mono text-[13px] text-ink-muted-light">Loading question…</p>
      )}
    </div>
  );
}
