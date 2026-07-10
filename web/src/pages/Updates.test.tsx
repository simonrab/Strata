import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Updates } from "./Updates";
import { diffFixture, reviewFixture } from "../test/fixtures";
import type { ReviewResult } from "../lib/types";

vi.mock("../lib/api", () => ({
  checkUpdates: vi.fn(),
  postUpdate: vi.fn(),
  getVersion: vi.fn(),
}));
import { checkUpdates, postUpdate, getVersion } from "../lib/api";

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

  it("checks for new trials and lists the real candidates the re-search found", async () => {
    vi.mocked(checkUpdates).mockResolvedValue([
      { nct_id: "NCT03496298", title: "AMPLITUDE-O" },
    ]);

    renderAt();
    await userEvent.click(
      screen.getByRole("button", { name: /check for new trials/i })
    );

    expect(await screen.findByText("NCT03496298")).toBeInTheDocument();
    expect(screen.getByText("AMPLITUDE-O")).toBeInTheDocument();
    expect(checkUpdates).toHaveBeenCalledWith("glp1-mace");
  });

  it("shows an honest empty state when nothing is new", async () => {
    vi.mocked(checkUpdates).mockResolvedValue([]);

    renderAt();
    await userEvent.click(
      screen.getByRole("button", { name: /check for new trials/i })
    );

    expect(await screen.findByText(/no new trials/i)).toBeInTheDocument();
  });

  it("injects a discovered trial, then shows the diff and highlighted new row", async () => {
    vi.mocked(checkUpdates).mockResolvedValue([
      { nct_id: "NCT03496298", title: "AMPLITUDE-O" },
    ]);
    vi.mocked(postUpdate).mockResolvedValue(diffFixture);
    vi.mocked(getVersion).mockImplementation((_id: string, v: number) =>
      Promise.resolve(v === diffFixture.previous_version ? reviewFixture : current)
    );

    renderAt();
    await userEvent.click(
      screen.getByRole("button", { name: /check for new trials/i })
    );
    await userEvent.click(await screen.findByRole("button", { name: /inject/i }));

    expect(await screen.findByText("Parameter Shifts")).toBeInTheDocument();
    expect(screen.getByText(/Benefit holds/i)).toBeInTheDocument();
    // The injected trial is highlighted in the updated forest plot.
    expect(screen.getByText("New")).toBeInTheDocument();
    expect(postUpdate).toHaveBeenCalledWith("glp1-mace", "NCT03496298");
  });
});
