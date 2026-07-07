import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { EvidenceLedger } from "./EvidenceLedger";
import { reviewFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({ getReview: vi.fn() }));
import { getReview } from "../lib/api";

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/reviews/${id}/evidence`]}>
      <Routes>
        <Route path="/reviews/:id/evidence" element={<EvidenceLedger />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("EvidenceLedger", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders PRISMA counts and one row per trial with HR and status", async () => {
    vi.mocked(getReview).mockResolvedValue(reviewFixture);
    renderAt("glp1-mace");

    expect(await screen.findByText("LEADER")).toBeInTheDocument();
    expect(screen.getByText(/0.87 \[0.78, 0.97\]/)).toBeInTheDocument();

    // PRISMA: 3 identified -> 2 assessed/passed -> 2 pooled.
    expect(screen.getByText("Identified")).toBeInTheDocument();
    expect(screen.getAllByText("Pooled").length).toBeGreaterThan(0);

    // The flagged, un-extracted trial surfaces as Review with its reason.
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText(/No hazard-ratio analysis/)).toBeInTheDocument();

    // A row links through to its extraction-confirmation page.
    expect(screen.getByText("LEADER").closest("a")).toHaveAttribute(
      "href",
      "/reviews/glp1-mace/evidence/NCT01179048"
    );
  });
});
