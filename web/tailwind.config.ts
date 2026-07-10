import type { Config } from "tailwindcss";

/**
 * Theme ported from the "Scientific Terminal" design system
 * (stitch_livemeta_precision_evidence_system/scientific_terminal/DESIGN.md).
 * Flat & hairline: no shadows, depth via tonal layering + 0.5px borders.
 */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // All colours resolve to the CSS-variable token layer in index.css so
        // the app themes light/dark by flipping one set of variables. The
        // light/dark object shape is kept so existing class names still work
        // (bg-canvas-light, …); both point at the same themed variable.
        canvas: { light: "var(--canvas)", dark: "var(--canvas)" },
        card: { light: "var(--card)", dark: "var(--card)" },
        hairline: { light: "var(--hairline)", dark: "var(--hairline)" },
        ink: { light: "var(--ink)", dark: "var(--ink)" },
        "ink-muted": { light: "var(--ink-muted)", dark: "var(--ink-muted)" },
        // Accent — interaction cues only
        accent: "var(--accent)",
        "accent-container": "var(--accent-container)",
        "accent-border": "var(--accent-border)",
        "on-accent-container": "var(--on-accent-container)",
        // Tonal surfaces
        surface: "var(--canvas)",
        "surface-container-lowest": "var(--card)",
        "surface-container-low": "var(--sunk)",
        "surface-container": "var(--surface-container)",
        "surface-container-high": "var(--surface-container-high)",
        "surface-container-highest": "var(--surface-container-highest)",
        "on-surface": "var(--ink)",
        "on-surface-variant": "var(--ink-muted)",
        outline: "var(--outline)",
        "outline-variant": "var(--outline-variant)",
        primary: "var(--primary)",
        "on-primary": "var(--on-primary)",
        secondary: "var(--secondary)",
        // Semantic — RoB / certainty only, always paired with a label
        "risk-low": "var(--risk-low)",
        "risk-some": "var(--risk-some)",
        "risk-high": "var(--risk-high)",
        "risk-low-container": "var(--risk-low-container)",
        "risk-some-container": "var(--risk-some-container)",
        "risk-high-container": "var(--risk-high-container)",
        error: "var(--risk-high)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
        // Serif is retired in the Meridian direction; mapped to the sans stack
        // so any lingering `font-serif` renders as Inter, not a display face.
        serif: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-xl": ["40px", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "500" }],
        "display-lg": ["32px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "600" }],
        "headline-md": ["20px", { lineHeight: "28px", fontWeight: "500" }],
        "section-sm": ["16px", { lineHeight: "24px", fontWeight: "500" }],
        "body-md": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "data-mono": ["13px", { lineHeight: "18px", fontWeight: "400" }],
        "label-caps": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "600" }],
        "clinical-conclusion": ["18px", { lineHeight: "28px", fontWeight: "400" }],
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },
      borderWidth: { hairline: "0.5px" },
      spacing: { gutter: "24px" },
    },
  },
  plugins: [],
} satisfies Config;
