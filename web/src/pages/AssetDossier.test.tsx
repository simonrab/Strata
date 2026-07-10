import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AssetDossier } from "./AssetDossier";
import type { AssetDossier as Dossier } from "../lib/types";

vi.mock("../lib/api", () => ({ getAssetDossier: vi.fn() }));
import { getAssetDossier } from "../lib/api";

const dossier: Dossier = {
  asset: { name: "Semaglutide", aliases: [], sponsor: "Novo Nordisk", provenance: [] },
  sources: ["ctgov", "pubmed", "openfda"],
  trials: [
    {
      nct_id: "NCT1", title: "STEP 1", asset_name: "Semaglutide", phase: "phase_3",
      status: "COMPLETED", enrollment: 1961, has_results: true, countries: ["United States"],
      indication: "Obesity", provenance: [],
    },
  ],
  countries: [{ country: "United States", trials: 1 }],
  events: [],
  readouts: [
    {
      nct_id: "NCT1", title: "STEP 1", asset_name: "Semaglutide", phase: "phase_3",
      has_results: true, countries: [], indication: "Obesity", results_posted_date: "2021-02-10",
      provenance: [],
    },
  ],
  approvals: [
    { drug: "Semaglutide", application_number: "NDA209637", brand_names: ["OZEMPIC"],
      approval_date: "2017-12-05", provenance: [] },
  ],
  sub_indications: [
    { signature: "obesity|cvd", label: "Obesity + established CVD", trial_ids: ["NCT1"],
      phases: ["phase_3"], evidence: { question_id: "q", measure: "HR", state: "pooled",
        estimate: 0.8, ci_low: 0.72, ci_high: 0.9, grade_certainty: "moderate",
        conclusion: "significant reduction", k: 6 } },
  ],
  notes: [],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/asset/Semaglutide"]}>
      <Routes>
        <Route path="/asset/:name" element={<AssetDossier />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AssetDossier", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders trials, geography, readouts, approvals, and sub-indications", async () => {
    vi.mocked(getAssetDossier).mockResolvedValue(dossier);
    renderPage();
    expect(await screen.findByText("Semaglutide")).toBeInTheDocument();
    expect(screen.getByText("Obesity + established CVD")).toBeInTheDocument();
    expect(screen.getByText(/OZEMPIC/)).toBeInTheDocument();
    expect(screen.getByText("NDA209637")).toBeInTheDocument();
    expect(screen.getByText(/United States/)).toBeInTheDocument();
    // pooled evidence badge from the sub-indication
    expect(screen.getByTestId("evidence-pooled")).toHaveTextContent("HR 0.80 [0.72, 0.90]");
  });

  it("shows a source toggle", async () => {
    vi.mocked(getAssetDossier).mockResolvedValue(dossier);
    renderPage();
    expect(await screen.findByText("Sources")).toBeInTheDocument();
  });

  it("expands a sub-indication to reveal its trials, joined from the dossier", async () => {
    vi.mocked(getAssetDossier).mockResolvedValue(dossier);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Obesity + established CVD");
    // The trial list is collapsed until the sub-indication is clicked.
    expect(screen.queryByTestId("subind-trials-obesity|cvd")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Obesity \+ established CVD/i })
    );

    const panel = await screen.findByTestId("subind-trials-obesity|cvd");
    // The trial is looked up from the dossier's full trial detail by its NCT id.
    expect(within(panel).getByText("STEP 1")).toBeInTheDocument();
    expect(within(panel).getByText("NCT1")).toBeInTheDocument();

    // Clicking again collapses it.
    await user.click(
      screen.getByRole("button", { name: /Obesity \+ established CVD/i })
    );
    expect(screen.queryByTestId("subind-trials-obesity|cvd")).not.toBeInTheDocument();
  });
});
