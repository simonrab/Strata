import { useState } from "react";
import type { Provenance } from "../lib/types";

// A snippet popover: every pooled number traces to the exact source snippet.
export function ProvenancePopover({ provenance }: { provenance: Provenance[] }) {
  const [open, setOpen] = useState(false);
  const first = provenance[0];
  if (!first) return null;

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        aria-label="Show source snippet"
        className="font-mono text-[11px] text-accent underline decoration-dotted underline-offset-2"
      >
        source
      </button>
      {open && (
        <span className="absolute left-0 top-5 z-20 block w-72 rounded-md hairline bg-card-light p-3 text-left shadow-none">
          <span className="block font-serif text-[13px] italic leading-5 text-ink-light">
            “{first.snippet}”
          </span>
          {first.source_url && (
            <a
              href={first.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 block font-mono text-[10px] uppercase tracking-wider text-accent"
            >
              {first.trial_id} · open source ↗
            </a>
          )}
        </span>
      )}
    </span>
  );
}
