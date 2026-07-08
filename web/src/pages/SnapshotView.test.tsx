import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { SnapshotView } from "./SnapshotView";
import { reviewFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({
  getVersion: vi.fn(),
}));
import { getVersion } from "../lib/api";

describe("SnapshotView", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a read-only report for a specific past version", async () => {
    vi.mocked(getVersion).mockResolvedValue(reviewFixture);
    render(
      <MemoryRouter initialEntries={["/reviews/glp1-mace/versions/1"]}>
        <Routes>
          <Route path="/reviews/:id/versions/:version" element={<SnapshotView />} />
        </Routes>
      </MemoryRouter>
    );
    expect(await screen.findByText(/Read-only/i)).toBeInTheDocument();
    // ReportView renders the pooled answer for that snapshot.
    expect(screen.getByText(/Pooled answer/i)).toBeInTheDocument();
    expect(getVersion).toHaveBeenCalledWith("glp1-mace", 1);
  });
});
