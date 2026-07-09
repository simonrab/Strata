import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ExtractionConfirmation } from "./ExtractionConfirmation";
import { reviewFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({ getReview: vi.fn(), postDecision: vi.fn() }));
import { getReview, postDecision } from "../lib/api";

function renderAt(trialId: string) {
  return render(
    <MemoryRouter initialEntries={[`/reviews/glp1-mace/evidence/${trialId}`]}>
      <Routes>
        <Route
          path="/reviews/:id/evidence/:trialId"
          element={<ExtractionConfirmation />}
        />
        <Route path="/reviews/:id/evidence" element={<div>Ledger</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ExtractionConfirmation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the trial's effect and source snippet", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    renderAt("NCT01179048");

    expect(
      await screen.findByText("HR 0.87 [0.78, 0.97]")
    ).toBeInTheDocument();
    expect(screen.getByText(/Primary outcome: HR 0.87/)).toBeInTheDocument();
  });

  it("posts a flag decision and returns to the ledger", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    vi.mocked(postDecision).mockResolvedValue(reviewFixture);
    renderAt("NCT01179048");

    await screen.findByText("HR 0.87 [0.78, 0.97]");
    await userEvent.click(screen.getByRole("button", { name: /Flag for review/i }));

    expect(postDecision).toHaveBeenCalledWith("glp1-mace", {
      study_id: "NCT01179048",
      decision: "flagged",
      reason: "Flagged during review",
    });
    expect(await screen.findByText("Ledger")).toBeInTheDocument();
  });
});
