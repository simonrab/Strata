import { useEffect, useState } from "react";
import type { Source } from "../lib/types";
import { FREE_TEXT_SOURCES, SOURCE_LABEL, STRUCTURED_SOURCES } from "../lib/types";
import { Icon } from "./Icon";

const KEY = "livemeta.sources";

// Persisted source selection. Authoritative (CT.gov / PubMed / openFDA) default
// on; free-text (announcements / filings) default off. The user opts in to the
// unverified, Claude-read sources.
export function loadSources(): Source[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Source[];
  } catch {
    /* ignore */
  }
  return [...STRUCTURED_SOURCES];
}

export function SourceToggle({
  value,
  onChange,
}: {
  value: Source[];
  onChange: (next: Source[]) => void;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  }, [value]);

  function toggle(s: Source) {
    onChange(value.includes(s) ? value.filter((x) => x !== s) : [...value, s]);
  }

  function row(s: Source) {
    return (
      <label
        key={s}
        className="flex cursor-pointer items-center gap-2 py-1 text-[13px] text-ink-light"
      >
        <input
          type="checkbox"
          checked={value.includes(s)}
          onChange={() => toggle(s)}
          className="accent-accent"
        />
        {SOURCE_LABEL[s]}
      </label>
    );
  }

  const activeCount = value.length;
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-sm hairline bg-card-light px-3 py-2 text-[13px] text-ink-light hover:bg-surface-container-low"
      >
        <Icon name="tune" size={16} className="text-ink-muted-light" />
        Sources
        <span className="rounded-full bg-surface-container-high px-1.5 text-[11px] text-ink-muted-light">
          {activeCount}
        </span>
      </button>
      {open && (
        <div className="absolute left-0 top-11 z-30 w-64 rounded-md hairline bg-card-light p-3">
          <p className="mb-1 text-label-caps uppercase text-ink-muted-light">Authoritative</p>
          {STRUCTURED_SOURCES.map(row)}
          <p className="mb-1 mt-3 text-label-caps uppercase text-ink-muted-light">
            Free-text · unverified
          </p>
          {FREE_TEXT_SOURCES.map(row)}
          <p className="mt-2 flex items-start gap-1 text-[11px] leading-snug text-ink-muted-light">
            <Icon name="info" size={13} />
            Free-text sources are Claude-read from announcements and filings; off by default.
          </p>
        </div>
      )}
    </div>
  );
}
