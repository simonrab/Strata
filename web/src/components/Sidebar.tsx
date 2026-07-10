import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Icon } from "./Icon";

const linkBase =
  "group flex items-center gap-3 rounded-sm px-3 py-2 text-label-caps transition-colors";

function item(active: boolean): string {
  return active
    ? `${linkBase} border-l-2 border-accent bg-accent-container pl-[10px] text-on-accent-container`
    : `${linkBase} text-ink-muted-light hover:bg-surface-container-low hover:text-ink-light`;
}

const primary = [
  { to: "/", label: "Reviews", end: true, icon: "space_dashboard" },
  { to: "/ask", label: "Ask", end: false, icon: "help_outline" },
  { to: "/landscape", label: "Landscape", end: false, icon: "hub" },
];

// The current review id, if we're inside a /reviews/:id/... route — so the
// analysis links can target it.
function useCurrentReviewId(): string | null {
  const { pathname } = useLocation();
  return pathname.match(/^\/reviews\/([^/]+)/)?.[1] ?? null;
}

// Explicit light/dark toggle. Stamps `light`/`dark` on <html>, which the token
// layer treats as an override that beats the OS `prefers-color-scheme`.
type Theme = "light" | "dark";
function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const el = document.documentElement;
    if (el.classList.contains("dark")) return "dark";
    if (el.classList.contains("light")) return "light";
    return systemTheme();
  });
  useEffect(() => {
    const el = document.documentElement;
    el.classList.remove("light", "dark");
    el.classList.add(theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

export function Sidebar() {
  const reviewId = useCurrentReviewId();
  const [theme, toggleTheme] = useTheme();
  const analysis = reviewId
    ? [
        { to: `/reviews/${reviewId}/report`, label: "Answer", icon: "description" },
        { to: `/reviews/${reviewId}/screening`, label: "Screening", icon: "filter_alt" },
        { to: `/reviews/${reviewId}/evidence`, label: "Evidence", icon: "database" },
        { to: `/reviews/${reviewId}/updates`, label: "Updates", icon: "sync" },
        { to: `/reviews/${reviewId}/rob`, label: "Risk of Bias", icon: "gavel" },
        { to: `/reviews/${reviewId}/grade`, label: "GRADE", icon: "analytics" },
        { to: `/reviews/${reviewId}/audit`, label: "Audit Trail", icon: "history" },
      ]
    : [];

  return (
    <aside className="hairline-r fixed left-0 top-0 z-40 hidden h-screen w-64 flex-col bg-surface-container-low py-6 md:flex">
      <div className="mb-8 flex items-center gap-3 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-on-primary">
          <svg
            viewBox="0 0 24 24"
            width="19"
            height="19"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M3 12h4l3-7 4 14 3-7h4" />
          </svg>
        </div>
        <div>
          <h1 className="font-sans text-headline-md font-bold leading-tight text-ink-light">
            Meridian
          </h1>
          <p className="text-label-caps uppercase text-ink-muted-light">Living evidence</p>
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
            <div className="mb-1 px-3 pb-1 text-label-caps uppercase text-outline">
              This review
            </div>
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
        <button
          type="button"
          onClick={toggleTheme}
          className={`${linkBase} w-full text-ink-muted-light hover:bg-surface-container-low hover:text-ink-light`}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <Icon name={theme === "dark" ? "light_mode" : "dark_mode"} size={18} />
          <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
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
