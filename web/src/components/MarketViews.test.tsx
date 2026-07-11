import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ChangeFeed } from "./ChangeFeed";
import { CompareView } from "./CompareView";
import { MoaView } from "./MoaView";
import type { AssetComparison, LandscapeDiff, MoaLandscape } from "../lib/types";

function wrap(ui: React.ReactNode) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("ChangeFeed", () => {
  it("renders an advance with its asset and the Advanced label", () => {
    const diff: LandscapeDiff = {
      condition: "Obesity",
      since: "2020-01-01",
      until: null,
      notes: [],
      changes: [
        {
          asset_name: "Retatrutide",
          indication: "Obesity",
          change_type: "advanced",
          date: "2026-06-18",
          from_phase: "phase_2",
          to_phase: "phase_3",
          summary: "Advanced Phase 2 → Phase 3",
          provenance: [],
        },
      ],
    };
    wrap(<ChangeFeed diff={diff} />);
    expect(screen.getByText("Retatrutide")).toBeTruthy();
    expect(screen.getByText("Advanced")).toBeTruthy();
  });

  it("shows an empty state when nothing moved", () => {
    const diff: LandscapeDiff = { condition: "Obesity", since: null, until: null, changes: [], notes: [] };
    wrap(<ChangeFeed diff={diff} />);
    expect(screen.getByText(/Nothing moved/i)).toBeTruthy();
  });
});

describe("CompareView (safety)", () => {
  const comparison: AssetComparison = {
    assets: ["Tirzepatide", "Semaglutide"],
    indication: "Obesity",
    notes: [],
    rows: [
      { label: "Lead phase", values: ["Phase 3", "Approved"], more: [false, false] },
      { label: "Enrollment", values: ["12,500", "17,600"], more: [false, true] },
    ],
    evidence: [
      { asset_name: "Tirzepatide", indication: "Obesity", population: "obesity", comparator: null,
        plain_summary: "benefit proven", badge: null },
      { asset_name: "Semaglutide", indication: "Obesity", population: "obesity", comparator: null,
        plain_summary: "benefit proven", badge: null },
    ],
    comparability: {
      directly_comparable: false,
      reasons: ["no common comparator established (unanchored indirect comparison)"],
    },
  };

  it("shows operational rows only and no pooled evidence", () => {
    wrap(<CompareView comparison={comparison} />);
    expect(screen.getByText("Lead phase")).toBeTruthy();
    // Pooled evidence is not shown on the market-intelligence surface.
    expect(screen.queryByText(/Pooled evidence/i)).toBeNull();
    expect(screen.queryByText(/not directly comparable/i)).toBeNull();
    expect(screen.queryByText(/benefit proven/i)).toBeNull();
  });

  it("renders the neutral 'more' marker on operational counts", () => {
    wrap(<CompareView comparison={comparison} />);
    // The larger enrollment carries a neutral marker (a fact), not a verdict.
    expect(screen.getByText("(more)")).toBeTruthy();
  });
});

describe("MoaView", () => {
  it("clusters by class and sinks unclassified to the bottom", () => {
    const moa: MoaLandscape = {
      condition: "Obesity",
      notes: [],
      clusters: [
        {
          drug_class: "GLP-1 receptor agonists", label: "GLP-1 receptor agonists",
          assets: ["Semaglutide", "Dulaglutide"], program_count: 2,
          stage_distribution: { phase_3: 1, phase_2: 1 }, plain_summary: "benefit proven", evidence: null,
        },
        {
          drug_class: "unclassified", label: "Unclassified", assets: ["Mysterymol"],
          program_count: 1, stage_distribution: { phase_1: 1 }, plain_summary: "no linked evidence", evidence: null,
        },
      ],
    };
    wrap(<MoaView moa={moa} />);
    expect(screen.getByText("GLP-1 receptor agonists")).toBeTruthy();
    expect(screen.getByText("Unclassified")).toBeTruthy();
    expect(screen.getByText(/class not inferred/i)).toBeTruthy();
  });
});
