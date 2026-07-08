import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuditTrail } from "./AuditTrail";
import { historyFixture } from "../test/fixtures";

vi.mock("../lib/api", () => ({
  getHistory: vi.fn(),
}));
import { getHistory } from "../lib/api";

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/reviews/glp1-mace/audit"]}>
      <Routes>
        <Route path="/reviews/:id/audit" element={<AuditTrail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("AuditTrail", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists snapshot versions with Current and Initial status labels", async () => {
    vi.mocked(getHistory).mockResolvedValue(historyFixture);
    renderAt();
    expect(await screen.findByText("Current")).toBeInTheDocument();
    expect(screen.getByText("Initial")).toBeInTheDocument();
    // The current version links to its read-only snapshot.
    const row = screen.getByText(/Run 2/).closest("a");
    expect(row).toHaveAttribute("href", "/reviews/glp1-mace/versions/2");
  });

  it("shows an empty state when there is no history", async () => {
    vi.mocked(getHistory).mockResolvedValue([]);
    renderAt();
    expect(await screen.findByText(/No runs yet/i)).toBeInTheDocument();
  });
});
