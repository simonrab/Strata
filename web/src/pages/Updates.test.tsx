import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Updates } from "./Updates";
import { diffFixture, reviewFixture } from "../test/fixtures";
import type { ReviewResult } from "../lib/types";

vi.mock("../lib/api", () => ({
  postUpdate: vi.fn(),
  getVersion: vi.fn(),
}));
import { postUpdate, getVersion } from "../lib/api";

// The current (v2) snapshot must contain the injected trial so the forest plot
// has a row to highlight.
const current: ReviewResult = {
  ...reviewFixture,
  pool: {
    ...reviewFixture.pool!,
    studies: [
      ...reviewFixture.pool!.studies,
      {
        study_id: "NCT03496298",
        label: "AMPLITUDE-O",
        yi: -0.31,
        vi: 0.02,
        effect: 0.73,
        ci_low: 0.58,
        ci_high: 0.92,
        weight: 20,
      },
    ],
  },
};

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/reviews/glp1-mace/updates"]}>
      <Routes>
        <Route path="/reviews/:id/updates" element={<Updates />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Updates", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the new-trial banner with an inject action", () => {
    renderAt();
    expect(screen.getByText(/New results posted/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /inject/i })).toBeInTheDocument();
  });

  it("injects the held-out trial, then shows the diff and highlighted new row", async () => {
    vi.mocked(postUpdate).mockResolvedValue(diffFixture);
    vi.mocked(getVersion).mockImplementation((_id: string, v: number) =>
      Promise.resolve(v === diffFixture.previous_version ? reviewFixture : current)
    );

    renderAt();
    await userEvent.click(screen.getByRole("button", { name: /inject/i }));

    expect(await screen.findByText("Parameter Shifts")).toBeInTheDocument();
    expect(screen.getByText(/Benefit holds/i)).toBeInTheDocument();
    // The injected trial is highlighted in the updated forest plot.
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(postUpdate).toHaveBeenCalledWith("glp1-mace", "NCT03496298");
  });
});
