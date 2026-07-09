import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CompetitorLandscape } from "./CompetitorLandscape";
import type { Landscape } from "../lib/types";

vi.mock("../lib/api", () => ({
  getLandscape: vi.fn(),
}));
import { getLandscape } from "../lib/api";

const landscape: Landscape = {
  condition: "Type 2 Diabetes",
  as_of: null,
  assets: ["Semaglutide", "Tirzepatide"],
  indications: ["Type 2 Diabetes"],
  cells: [
    {
      asset_name: "Semaglutide",
      indication: "Type 2 Diabetes",
      current_phase: "phase_3",
      sponsor: "Novo Nordisk",
      conflict: false,
      question_id: "glp1-mace",
      evidence: {
        question_id: "glp1-mace",
        measure: "HR",
        state: "pooled",
        estimate: 0.86,
        ci_low: 0.79,
        ci_high: 0.93,
        grade_certainty: "moderate",
        conclusion: "significant reduction",
        version: 3,
        k: 6,
      },
      provenance: [],
    },
    {
      asset_name: "Tirzepatide",
      indication: "Type 2 Diabetes",
      current_phase: "phase_2",
      sponsor: "Eli Lilly",
      conflict: true,
      conflict_note: "sources disagree",
      evidence: {
        question_id: "tirz",
        measure: "HR",
        state: "gate_open",
        conclusion: "pooling withheld pending homogeneity confirmation",
        k: 0,
      },
      provenance: [],
    },
  ],
  notes: [],
};

describe("CompetitorLandscape", () => {
  beforeEach(() => vi.clearAllMocks());

  function renderPage() {
    return render(
      <MemoryRouter>
        <CompetitorLandscape />
      </MemoryRouter>
    );
  }

  it("renders the assets × indications matrix with stage pills", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    expect(await screen.findByTestId("landscape-matrix")).toBeInTheDocument();
    expect(screen.getByText("Semaglutide")).toBeInTheDocument();
    expect(screen.getByText("Tirzepatide")).toBeInTheDocument();
    expect(screen.getByText("Phase 3")).toBeInTheDocument();
  });

  it("shows the pooled evidence badge and the homogeneity-gate state", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    expect(await screen.findByTestId("evidence-pooled")).toHaveTextContent(
      "HR 0.86 [0.79, 0.93]"
    );
    expect(screen.getByTestId("evidence-pooled")).toHaveTextContent(/GRADE moderate/);
    expect(screen.getByTestId("evidence-gate")).toBeInTheDocument();
  });

  it("flags a cell where sources conflict", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    expect(await screen.findByLabelText("source conflict")).toBeInTheDocument();
  });

  it("re-fetches with an as-of date when the time slider moves", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    await screen.findByTestId("landscape-matrix");

    fireEvent.change(screen.getByLabelText("as of year"), { target: { value: "2015" } });

    await waitFor(() =>
      expect(getLandscape).toHaveBeenCalledWith("Obesity", "2015-12-31")
    );
    expect(screen.getByTestId("as-of-label")).toHaveTextContent("Dec 2015");
  });
});
