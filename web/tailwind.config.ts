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
        // Canvas & cards (Level 0 / Level 1)
        canvas: { light: "#f9f9f9", dark: "#000000" },
        card: { light: "#ffffff", dark: "#0e0f0f" },
        hairline: { light: "#e5e5e5", dark: "#26282b" },
        // Ink
        ink: { light: "#1a1c1c", dark: "#f1f1f1" },
        "ink-muted": { light: "#434747", dark: "#b4b2a9" },
        // Accent — interaction cues only
        accent: "#2563eb",
        "accent-container": "#eff6ff",
        "accent-border": "#bfdbfe",
        "on-accent-container": "#1e3a8a",
        // Material tokens (from DESIGN.md front-matter)
        surface: "#f9f9f9",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f3f3f3",
        "surface-container": "#eeeeee",
        "surface-container-high": "#e8e8e8",
        "surface-container-highest": "#e2e2e2",
        "on-surface": "#1a1c1c",
        "on-surface-variant": "#434747",
        outline: "#747878",
        "outline-variant": "#c4c7c7",
        primary: "#000000",
        "on-primary": "#ffffff",
        secondary: "#0051d5",
        // Semantic — RoB / certainty only, always paired with a label
        "risk-low": "#15803d",
        "risk-some": "#b45309",
        "risk-high": "#ba1a1a",
        "risk-low-container": "#dcfce7",
        "risk-some-container": "#fef3c7",
        "risk-high-container": "#fee2e2",
        error: "#ba1a1a",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
        serif: ["'Source Serif 4'", "Georgia", "serif"],
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
