import { useState } from "react";
import { marketAsk } from "../lib/api";
import type { MarketAnswer } from "../lib/types";
import { Icon } from "../components/Icon";
import { MarketResult } from "../components/MarketResult";

// The market-intelligence front door. Ask in plain language; the router picks the
// right tool and this renders that tool's real view inline, with a grounded
// narrative and follow-up chips. Deterministic figures — the model only routes.
// The prompt box mirrors the "New review" (Ask) box: a large rounded card with a
// textarea and an inline accent send button.

interface Turn {
  question: string;
  answer?: MarketAnswer;
  error?: boolean;
}

const STARTERS = [
  "Map the obesity landscape",
  "What changed in obesity since 2023",
  "Compare tirzepatide and semaglutide",
  "Upcoming readouts in obesity",
  "Group obesity by mechanism",
];

export function MarketHub() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const empty = turns.length === 0;

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    const idx = turns.length;
    setTurns((t) => [...t, { question: q }]);
    try {
      const answer = await marketAsk(q);
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, answer } : turn)));
    } catch {
      setTurns((t) => t.map((turn, i) => (i === idx ? { ...turn, error: true } : turn)));
    } finally {
      setBusy(false);
    }
  }

  // The prompt box, styled to mirror the New review (Ask) box.
  const promptBox = (rows: number) => (
    <div className="relative rounded-2xl hairline bg-card-light shadow-sm transition-colors focus-within:border-accent">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            ask(input);
          }
        }}
        rows={rows}
        aria-label="market question"
        placeholder="Ask about assets, indications, timing, or what moved…"
        className="max-h-64 w-full resize-none overflow-y-auto rounded-2xl bg-transparent p-4 pr-14 text-left text-[16px] leading-7 text-ink-light outline-none placeholder:text-ink-muted-light"
      />
      <button
        onClick={() => ask(input)}
        disabled={!input.trim() || busy}
        aria-label="send"
        title="Send (↵)"
        className="absolute bottom-3 right-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Icon name={busy ? "more_horiz" : "arrow_upward"} size={18} />
      </button>
    </div>
  );

  // Empty state: a centered hero, mirroring the New review page.
  if (empty) {
    return (
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-6 py-10 text-center">
        <p className="text-label-caps uppercase text-ink-muted-light">Market intelligence</p>
        <h1 className="mt-3 font-sans text-display-lg text-ink-light">
          What do you want to know about the clinical trial landscape?
        </h1>

        <div className="mt-8 w-full">
          {promptBox(4)}
          <p className="mt-3 text-[12px] text-ink-muted-light">
            Market intelligence over live ClinicalTrials.gov — a research tool, not medical advice.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {STARTERS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => ask(s)}
              className="rounded-full hairline bg-card-light px-3.5 py-1.5 text-[13px] text-ink-muted-light hover:text-ink-light"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Active state: transcript above, the same prompt box docked below.
  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-6 py-10">
      <div className="flex-1 space-y-6">
        {turns.map((turn, i) => (
          <div key={i}>
            <div className="mb-3 flex justify-end">
              <div className="max-w-[80%] rounded-xl rounded-br-sm bg-accent-container px-3.5 py-2 text-[13px] text-on-accent-container">
                {turn.question}
              </div>
            </div>

            {turn.error && (
              <p className="font-mono text-[13px] text-risk-high">
                Could not answer that. Is the backend running on :8000?
              </p>
            )}

            {turn.answer && (
              <div className="flex gap-3">
                <div className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-primary text-on-primary">
                  <Icon name="auto_awesome" size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="mb-3 text-[13px] leading-relaxed text-ink-light">
                    {turn.answer.narrative}
                  </p>
                  <MarketResult answer={turn.answer} />
                  {turn.answer.suggestions.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {turn.answer.suggestions.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => ask(s)}
                          className="inline-flex items-center gap-1 rounded-full hairline bg-surface-container-low px-3 py-1 text-[12px] text-ink-muted-light hover:text-ink-light"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {!turn.answer && !turn.error && (
              <div className="flex items-center gap-2 text-[13px] text-ink-muted-light">
                <Icon name="progress_activity" size={16} className="animate-spin" />
                Working…
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="sticky bottom-6 mt-6">{promptBox(2)}</div>
    </div>
  );
}
