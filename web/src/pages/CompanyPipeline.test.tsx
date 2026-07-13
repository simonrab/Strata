import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CompanyPipeline } from "./CompanyPipeline";
import type { CompanyPipeline as Pipeline } from "../lib/types";

vi.mock("../lib/api", () => ({
  getCompanyPipeline: vi.fn(),
}));
import { getCompanyPipeline } from "../lib/api";

const pipeline: Pipeline = {
  sponsor: "Novo Nordisk",
  as_of: null,
  assets: ["Semaglutide", "Ziltivekimab"],
  indications: ["Type 2 Diabetes", "Obesity", "Heart Failure"],
  cells: [
    {
      asset_name: "Semaglutide",
      indication: "Type 2 Diabetes",
      current_phase: "phase_3",
      sponsor: "Novo Nordisk",
      conflict: false,
      provenance: [],
    },
    {
      asset_name: "Semaglutide",
      indication: "Obesity",
      current_phase: "phase_2",
      sponsor: "Novo Nordisk",
      conflict: false,
      provenance: [],
    },
    {
      asset_name: "Ziltivekimab",
      indication: "Heart Failure",
      current_phase: "phase_1",
      sponsor: "Novo Nordisk",
      conflict: false,
      provenance: [],
    },
  ],
  approvals: [
    {
      drug: "Semaglutide",
      sponsor: "Novo Nordisk",
      application_number: "NDA209637",
      brand_names: ["OZEMPIC"],
      approval_date: "2017-12-05",
      marketing_status: "Prescription",
      provenance: [],
    },
  ],
  notes: [],
};

describe("CompanyPipeline", () => {
  beforeEach(() => vi.clearAllMocks());

  function renderPage() {
    return render(
      <MemoryRouter initialEntries={["/company/Novo%20Nordisk"]}>
        <Routes>
          <Route path="/company/:name" element={<CompanyPipeline />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("shows the company's assets across multiple indications, in phase columns", async () => {
    vi.mocked(getCompanyPipeline).mockResolvedValue(pipeline);
    renderPage();

    // The decoded sponsor name is the heading, and the page fetched by it.
    expect(await screen.findByRole("heading", { name: "Novo Nordisk" })).toBeInTheDocument();
    expect(getCompanyPipeline).toHaveBeenCalledWith(expect.anything(), null, ["ctgov"]);

    // The same asset appears in two different phase columns (one per indication).
    const phase3 = screen.getByTestId("phase-col-phase_3");
    const phase2 = screen.getByTestId("phase-col-phase_2");
    expect(within(phase3).getByText("Semaglutide")).toBeInTheDocument();
    expect(within(phase2).getByText("Semaglutide")).toBeInTheDocument();
    expect(screen.getByTestId("phase-col-phase_1")).toBeInTheDocument();
  });

  it("does not render an FDA approvals section (openFDA disabled)", async () => {
    vi.mocked(getCompanyPipeline).mockResolvedValue(pipeline);
    renderPage();

    await screen.findByRole("heading", { name: "Novo Nordisk" });
    // The openFDA approvals surface was removed: no section, no stat, no app no.
    expect(screen.queryByTestId("approvals-list")).not.toBeInTheDocument();
    expect(screen.queryByText("FDA approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("NDA209637")).not.toBeInTheDocument();
  });

  it("narrows the board to one indication via the filter", async () => {
    vi.mocked(getCompanyPipeline).mockResolvedValue(pipeline);
    renderPage();
    await screen.findByTestId("pipeline-board");

    // Heart Failure only holds Ziltivekimab; filtering hides the Semaglutide cells.
    fireEvent.click(screen.getByRole("button", { name: "Heart Failure" }));
    expect(screen.getByText("Ziltivekimab")).toBeInTheDocument();
    expect(screen.queryByText("Semaglutide")).not.toBeInTheDocument();
  });

  it("re-fetches with an as-of date when the time slider moves", async () => {
    vi.mocked(getCompanyPipeline).mockResolvedValue(pipeline);
    renderPage();
    await screen.findByTestId("pipeline-board");

    fireEvent.change(screen.getByLabelText("as of year"), { target: { value: "2015" } });
    await waitFor(() =>
      expect(getCompanyPipeline).toHaveBeenCalledWith(expect.anything(), "2015-12-31", ["ctgov"])
    );
  });
});
