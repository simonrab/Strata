import { NavLink, useLocation } from "react-router-dom";
import { Icon } from "./Icon";

const linkBase =
  "group flex items-center gap-3 rounded-sm px-3 py-2 text-label-caps transition-colors";

function item(active: boolean): string {
  return active
    ? `${linkBase} border-l-2 border-accent bg-accent-container pl-[10px] text-accent`
    : `${linkBase} text-ink-muted-light hover:bg-surface-container-low hover:text-ink-light`;
}

const primary = [
  { to: "/", label: "Dashboard", end: true, icon: "space_dashboard" },
  { to: "/ask", label: "Ask", end: false, icon: "help_outline" },
];

// The current review id, if we're inside a /reviews/:id/... route — so the
// analysis links can target it.
function useCurrentReviewId(): string | null {
  const { pathname } = useLocation();
  return pathname.match(/^\/reviews\/([^/]+)/)?.[1] ?? null;
}

export function Sidebar() {
  const reviewId = useCurrentReviewId();
  const analysis = reviewId
    ? [
        { to: `/reviews/${reviewId}/evidence`, label: "Evidence", icon: "database" },
        { to: `/reviews/${reviewId}/report`, label: "Report", icon: "description" },
        { to: `/reviews/${reviewId}/updates`, label: "Updates", icon: "sync" },
        { to: `/reviews/${reviewId}/rob`, label: "Risk of Bias", icon: "gavel" },
        { to: `/reviews/${reviewId}/grade`, label: "GRADE", icon: "analytics" },
        { to: `/reviews/${reviewId}/audit`, label: "Audit Trail", icon: "history" },
      ]
    : [];

  return (
    <aside className="hairline-r fixed left-0 top-0 z-40 hidden h-screen w-64 flex-col bg-surface-container-low py-6 md:flex">
      <div className="mb-8 flex items-center gap-3 px-5">
        <div className="hairline flex h-9 w-9 items-center justify-center rounded-full bg-primary font-mono text-[14px] font-bold text-on-primary">
          L
        </div>
        <div>
          <h1 className="font-sans text-headline-md font-bold leading-tight text-ink-light">
            LiveMeta
          </h1>
          <p className="text-label-caps uppercase text-ink-muted-light">Clinical Terminal</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {primary.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => item(isActive)}>
            {({ isActive }) => (
              <>
                <Icon name={l.icon} size={20} fill={isActive} />
                <span>{l.label}</span>
              </>
            )}
          </NavLink>
        ))}

        {analysis.length > 0 && (
          <div className="pt-5">
            <div className="mb-1 px-3 pb-1 text-label-caps uppercase text-outline">Analysis</div>
            {analysis.map((l) => (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => item(isActive)}>
                {({ isActive }) => (
                  <>
                    <Icon name={l.icon} size={20} fill={isActive} />
                    <span>{l.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        )}
      </nav>

      <div className="hairline-t mx-3 mt-auto space-y-1 px-0 pt-4">
        {[
          { label: "Export", icon: "download" },
          { label: "Settings", icon: "settings" },
        ].map((l) => (
          <span
            key={l.label}
            className="flex cursor-not-allowed items-center gap-3 rounded-sm px-3 py-2 text-label-caps text-outline-variant opacity-70"
            title="Coming in a later slice"
          >
            <Icon name={l.icon} size={18} />
            <span>{l.label}</span>
          </span>
        ))}
      </div>
    </aside>
  );
}
