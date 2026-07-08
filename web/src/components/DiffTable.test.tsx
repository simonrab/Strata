import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffTable } from "./DiffTable";
import { diffFixture, reviewFixture } from "../test/fixtures";

describe("DiffTable", () => {
  it("shows the before/after parameter shifts and a benefit-holds verdict", () => {
    render(
      <DiffTable diff={diffFixture} previous={reviewFixture} current={reviewFixture} />
    );
    expect(screen.getByText("Parameter Shifts")).toBeInTheDocument();
    expect(screen.getByText(/v1 → v2/)).toBeInTheDocument();
    // The point estimate moved from 0.88 to 0.86.
    expect(screen.getByText("0.88")).toBeInTheDocument();
    expect(screen.getByText("0.86")).toBeInTheDocument();
    // k grew 7 -> 8 as the trial was added.
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    // Conclusion unchanged -> the benefit holds.
    expect(screen.getByText(/Benefit holds/i)).toBeInTheDocument();
  });

  it("reports a moved conclusion when the significance flips", () => {
    const moved = { ...diffFixture, conclusion_changed: true, significance_changed: true };
    render(<DiffTable diff={moved} previous={reviewFixture} current={reviewFixture} />);
    expect(screen.getByText(/Conclusion moved/i)).toBeInTheDocument();
  });
});
