import { NavLink, useLocation } from "react-router-dom";

const linkBase =
  "flex items-center gap-3 rounded-sm px-3 py-2 text-[12px] font-semibold uppercase tracking-wider transition-colors";

function item(active: boolean): string {
  return active
    ? `${linkBase} bg-surface-container-high text-secondary border-r-2 border-secondary`
    : `${linkBase} text-ink-muted-light hover:bg-surface-container-high`;
}

const primary = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/ask", label: "Ask", end: false },
];

// The current review id, if we're inside a /reviews/:id/... route — so the
// analysis links can target it.
function useCurrentReviewId(): string | null {
  const { pathname } = useLocation();
  return pathname.match(/^\/reviews\/([^/]+)/)?.[1] ?? null;
}

const disabledFooter = ["Export", "Settings"];

export function Sidebar() {
  const reviewId = useCurrentReviewId();
  const analysis = reviewId
    ? [
        { to: `/reviews/${reviewId}/updates`, label: "Updates" },
        { to: `/reviews/${reviewId}/rob`, label: "Risk of Bias" },
        { to: `/reviews/${reviewId}/grade`, label: "GRADE" },
        { to: `/reviews/${reviewId}/audit`, label: "Audit Trail" },
      ]
    : [];
  return (
    <aside className="fixed left-0 top-0 z-40 hidden h-screen w-64 flex-col border-r border-hairline-light bg-surface-container-low py-6 md:flex">
      <div className="mb-8 flex items-center gap-3 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-primary font-mono text-[12px] font-bold text-on-primary">
          LM
        </div>
        <div>
          <h1 className="font-sans text-[18px] font-bold leading-tight text-ink-light">
            LiveMeta
          </h1>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted-light">
            Clinical Terminal
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {primary.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => item(isActive)}>
            {l.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto space-y-1 border-t border-hairline-light px-3 pt-4">
        {analysis.length > 0 && (
          <div className="mb-1 px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-outline">
            Analysis
          </div>
        )}
        {analysis.map((l) => (
          <NavLink key={l.to} to={l.to} className={({ isActive }) => item(isActive)}>
            {l.label}
          </NavLink>
        ))}
        {disabledFooter.map((label) => (
          <span
            key={label}
            className="flex cursor-not-allowed items-center gap-3 rounded-sm px-3 py-1.5 text-[12px] font-semibold uppercase tracking-wider text-outline-variant"
            title="Coming in a later slice"
          >
            {label}
          </span>
        ))}
      </div>
    </aside>
  );
}
