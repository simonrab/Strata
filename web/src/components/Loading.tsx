// A small animated ring spinner, tinted with the accent color. Use inline where
// a compact loading cue is needed; use LoadingState for a page-level block.
export function Spinner({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className="animate-spin text-accent"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        className="opacity-20"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

// A centered loading block for a whole view: an animated spinner plus a label,
// so an in-flight fetch reads clearly as "loading" rather than a blank page.
export function LoadingState({ label }: { label: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-6 flex flex-col items-center justify-center gap-3 rounded-md hairline bg-card-light px-6 py-12 text-center"
    >
      <Spinner size={30} />
      <p className="font-mono text-[13px] text-ink-muted-light">{label}</p>
    </div>
  );
}
