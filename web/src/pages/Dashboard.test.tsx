import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Dashboard } from "./Dashboard";
import { summariesFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({
  listReviews: vi.fn(),
}));
import { listReviews } from "../lib/api";

describe("Dashboard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists saved reviews with their pooled estimate", async () => {
    vi.mocked(listReviews).mockResolvedValue(summariesFixture);
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    expect(
      await screen.findByText("Do GLP-1 receptor agonists reduce MACE versus placebo?")
    ).toBeInTheDocument();
    expect(screen.getByText(/HR 0.86 \[0.79, 0.94\]/)).toBeInTheDocument();
    // Row links to the review's evidence ledger.
    const row = screen.getByText(/reduce MACE/).closest("a");
    expect(row).toHaveAttribute("href", "/reviews/glp1-mace/evidence");
  });

  it("renders the living status pill for each review", async () => {
    vi.mocked(listReviews).mockResolvedValue([
      { ...summariesFixture[0], status: "estimate-updated" },
      {
        ...summariesFixture[0],
        question_id: "sglt2-hf",
        text: "Do SGLT2 inhibitors reduce heart-failure hospitalization?",
        status: "conclusion-moved",
      },
    ]);
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText("Estimate updated")).toBeInTheDocument();
    expect(screen.getByText("Conclusion moved")).toBeInTheDocument();
  });

  it("shows an empty state when there are no reviews", async () => {
    vi.mocked(listReviews).mockResolvedValue([]);
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText(/No reviews yet/)).toBeInTheDocument();
  });
});
