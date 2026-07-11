import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
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
  assets: ["Semaglutide", "Tirzepatide", "Retatrutide"],
  indications: ["Type 2 Diabetes", "Obesity"],
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
    {
      asset_name: "Retatrutide",
      indication: "Obesity",
      current_phase: "phase_2",
      sponsor: "Eli Lilly",
      conflict: false,
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

  it("renders a pipeline board with a column per occupied phase", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    expect(await screen.findByTestId("pipeline-board")).toBeInTheDocument();
    expect(screen.getByTestId("phase-col-phase_3")).toBeInTheDocument();
    expect(screen.getByTestId("phase-col-phase_2")).toBeInTheDocument();
    // No asset sits in Phase 1, so that column is not rendered.
    expect(screen.queryByTestId("phase-col-phase_1")).not.toBeInTheDocument();
  });

  it("places each asset card in its current-phase column", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    const phase3 = await screen.findByTestId("phase-col-phase_3");
    expect(within(phase3).getByText("Semaglutide")).toBeInTheDocument();

    const phase2 = screen.getByTestId("phase-col-phase_2");
    expect(within(phase2).getByText("Tirzepatide")).toBeInTheDocument();
    expect(within(phase2).getByText("Retatrutide")).toBeInTheDocument();
    // Semaglutide is not duplicated into Phase 2.
    expect(within(phase2).queryByText("Semaglutide")).not.toBeInTheDocument();
  });

  it("does not show pooled meta-analysis evidence on the market-intelligence surface", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    // Even though the cells carry evidence data, the market view never renders it —
    // pooled evidence lives in the review pages.
    await screen.findByText("Semaglutide");
    expect(screen.queryByTestId("evidence-pooled")).not.toBeInTheDocument();
    expect(screen.queryByTestId("evidence-gate")).not.toBeInTheDocument();
  });

  it("links the card name to the full asset dossier and keeps the condition timeline chip", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    const phase3 = await screen.findByTestId("phase-col-phase_3");

    // The drug name opens the cross-indication dossier.
    const dossierLink = within(phase3).getByRole("link", { name: "Semaglutide" });
    expect(dossierLink).toHaveAttribute("href", "/asset/Semaglutide");

    // The small Timeline chip still points at the condition-scoped timeline
    // (the board's active condition, which defaults to Obesity).
    const timelineLink = within(phase3).getByRole("link", { name: /Timeline/ });
    expect(timelineLink).toHaveAttribute(
      "href",
      "/landscape/asset/Semaglutide?condition=Obesity"
    );
  });

  it("links a card's sponsor to that company's entire pipeline", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    const phase3 = await screen.findByTestId("phase-col-phase_3");
    const sponsorLink = within(phase3).getByRole("link", { name: "Novo Nordisk" });
    expect(sponsorLink).toHaveAttribute("href", "/company/Novo%20Nordisk");
  });

  it("flags a card where sources conflict", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    expect(await screen.findByLabelText("source conflict")).toBeInTheDocument();
  });

  it("filters the board to one indication when its chip is clicked", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    await screen.findByTestId("pipeline-board");
    expect(screen.getByText("Semaglutide")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Obesity" }));

    expect(screen.getByText("Retatrutide")).toBeInTheDocument();
    expect(screen.queryByText("Semaglutide")).not.toBeInTheDocument();
    expect(screen.queryByText("Tirzepatide")).not.toBeInTheDocument();
  });

  it("re-fetches with an as-of date when the time slider moves", async () => {
    vi.mocked(getLandscape).mockResolvedValue(landscape);
    renderPage();
    await screen.findByTestId("pipeline-board");

    fireEvent.change(screen.getByLabelText("as of year"), { target: { value: "2015" } });

    await waitFor(() =>
      expect(getLandscape).toHaveBeenCalledWith("Obesity", "2015-12-31")
    );
    expect(screen.getByTestId("as-of-label")).toHaveTextContent("Dec 2015");
  });
});
