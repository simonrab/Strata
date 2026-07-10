import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Screening } from "./Screening";
import { reviewFixture } from "../test/fixtures";
import type { ReviewResult } from "../lib/types";

vi.mock("../lib/api", () => ({
  getReview: vi.fn(),
  postScreeningDecision: vi.fn(),
}));
import { getReview, postScreeningDecision } from "../lib/api";

const review: ReviewResult = {
  ...reviewFixture,
  screening: [
    {
      study_id: "NCT01",
      decision: "included",
      reason: "Adults with T2D — matches the PICO.",
      quote: { trial_id: "NCT01", snippet: "Adults aged 40-75 with type 2 diabetes." },
      by_claude: true,
      confirmed: false,
    },
    {
      study_id: "NCT02",
      decision: "excluded",
      domain: "population",
      reason: "Enrolled children, not the adult population.",
      by_claude: true,
      confirmed: false,
    },
  ],
};

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/reviews/glp1-mace/screening"]}>
      <Routes>
        <Route path="/reviews/:id/screening" element={<Screening />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Screening", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists each eligibility decision with its reason and disposition", async () => {
    vi.mocked(getReview).mockResolvedValue(review);
    renderAt();

    expect(await screen.findByText("NCT01")).toBeInTheDocument();
    expect(screen.getByText("NCT02")).toBeInTheDocument();
    expect(screen.getByText(/matches the PICO/i)).toBeInTheDocument();
    expect(screen.getByText(/Enrolled children/i)).toBeInTheDocument();
  });

  it("confirms a decision by re-sending the same disposition", async () => {
    vi.mocked(getReview).mockResolvedValue(review);
    vi.mocked(postScreeningDecision).mockResolvedValue(review);
    const user = userEvent.setup();
    renderAt();

    const row = (await screen.findByText("NCT01")).closest("[data-testid='screen-row']")!;
    await user.click(within(row as HTMLElement).getByRole("button", { name: /confirm/i }));

    expect(postScreeningDecision).toHaveBeenCalledWith("glp1-mace", {
      study_id: "NCT01",
      decision: "included",
    });
  });

  it("overrides a decision by sending the opposite disposition", async () => {
    vi.mocked(getReview).mockResolvedValue(review);
    vi.mocked(postScreeningDecision).mockResolvedValue(review);
    const user = userEvent.setup();
    renderAt();

    const row = (await screen.findByText("NCT02")).closest("[data-testid='screen-row']")!;
    // NCT02 was excluded — overriding re-admits it.
    await user.click(
      within(row as HTMLElement).getByRole("button", { name: /re-include/i })
    );

    expect(postScreeningDecision).toHaveBeenCalledWith("glp1-mace", {
      study_id: "NCT02",
      decision: "included",
    });
  });
});
