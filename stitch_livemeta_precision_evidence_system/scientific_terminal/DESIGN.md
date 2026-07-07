---
name: Scientific Terminal
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#434747'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#747878'
  outline-variant: '#c4c7c7'
  surface-tint: '#5d5f5e'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1a1c1c'
  on-primary-container: '#838484'
  inverse-primary: '#c6c6c6'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1a1c1c'
  on-tertiary-container: '#838484'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2e2e2'
  primary-fixed-dim: '#c6c6c6'
  on-primary-fixed: '#1a1c1c'
  on-primary-fixed-variant: '#454747'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c6'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  section-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  clinical-conclusion:
    fontFamily: Source Serif 4
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  xxl: 32px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style
The design system is engineered for "Scientific Terminal" precision—a tool for clinical researchers and medical reviewers where clarity is the only priority. The brand personality is authoritative, calm, and meticulous, drawing inspiration from the structured density of medical journals and the high-performance utility of Bloomberg-style data terminals.

The style is strictly **Flat & Hairline**. It avoids all decorative flourishes, including gradients and shadows. Depth is achieved exclusively through tonal layering (shifting background grays) and 0.5px hairline borders. The emotional response should be one of extreme focus, reliability, and objective truth.

## Colors
The palette is hyper-restrained to minimize cognitive load. 

- **Canvas & Card:** Light mode uses a subtle #F9F9F9 canvas with pure #FFFFFF cards. Dark mode utilizes a true #000000 canvas with #0E0F0F cards.
- **Ink:** Primary text is high-contrast (#1A1C1C Light / #F1F1F1 Dark), while secondary data uses a muted variant (#434655 Light / #B4B2A9 Dark).
- **Hairlines:** All structural separation uses 0.5px borders (#E5E5E5 Light / #26282B Dark).
- **Accent:** #2563EB is reserved strictly for interaction cues (links, focus rings, and active state indicators).
- **Semantic Logic:** Green, Amber, and Red are used only for risk-of-bias and certainty assessments, always paired with textual labels or symbolic icons to ensure accessibility.

## Typography
This design system employs a three-family typographic strategy to categorize information types:

1.  **Inter:** Used for all standard UI elements, navigation, and labels. Use sentence case for most interface text. Use `label-caps` for table headers and sidebar categories.
2.  **Source Serif 4:** Reserved exclusively for high-level clinical conclusions, summaries, and executive abstracts. This distinguishes human interpretation from raw data.
3.  **JetBrains Mono:** Used for all quantitative data, trial IDs, p-values, and confidence intervals. This ensures tabular figures align vertically and look "calculated."

## Layout & Spacing
The layout follows a **Fixed Grid** philosophy on desktop (to maintain "Terminal" density) and a fluid layout on mobile. 

- **Grid:** 12-column layout with 24px gutters.
- **Density:** Use tight spacing (4px/8px) for internal component grouping and wider spacing (24px/32px) for major section breaks.
- **Alignment:** Data tables should be flush with container edges, using horizontal hairlines for row separation.
- **Breakpoints:**
  - **Mobile (<768px):** Single column, 16px margins, bottom-sheet navigation.
  - **Desktop (>1024px):** Fixed-width sidebars (280px) and multi-pane clinical views.

## Elevation & Depth
Depth is strictly non-optical. No box-shadows or blurs are permitted.

- **Level 0 (Canvas):** #F9F9F9 (Light) / #000000 (Dark).
- **Level 1 (Cards/Panels):** #FFFFFF (Light) / #0E0F0F (Dark).
- **Level 2 (In-panel elements/Popovers):** Defined by 0.5px hairlines (#E5E5E5).
- **Modals:** Use a solid 1px border. The backdrop "dimmer" should be a high-opacity solid color rather than a soft blur.

## Shapes
The shape language balances modern software aesthetics with industrial precision.

- **Large Containers:** Cards, modals, and main content areas use a **12px radius** for a professional feel.
- **Interactive Elements:** Buttons, input fields, and dropdowns use a **4px radius** to feel more technical and "clickable."
- **Status Pills:** Tags and binary status indicators use a **full (pill) radius**.
- **Icons:** Use **Material Symbols Outlined**, 20px default size, with a weight of 300 (thin) to match the hairline aesthetic.

## Components
- **Buttons:** 
  - *Primary:* Solid Ink (#1A1C1C / #F1F1F1) with inverted text. No hover shadow; use opacity shift (90%) for hover.
  - *Secondary:* Ghost style with 0.5px hairline border.
- **Data Tables:** Use `data-mono` for all numerical cells. Header cells use `label-caps`. 0.5px horizontal borders only.
- **Focus States:** A 2px solid #2563EB ring with a 2px offset for all keyboard/active focus.
- **Inputs:** 4px radius, 0.5px border. On focus, the border color changes to #2563EB.
- **Risk Indicator:** A square icon or pill using semantic colors (Green/Amber/Red) to denote bias risk in trials.
- **Trial Cards:** Use 12px roundedness, white background, and a hairline border. Group metadata using `label-caps` for keys and `data-mono` for values.