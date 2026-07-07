import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ForestPlot } from "./ForestPlot";
import type { PoolResult } from "../lib/types";

const pool: PoolResult = {
  measure: "HR",
  model: "random",
  method: "REML",
  engine: "python",
  k: 2,
  estimate: 0.86,
  ci_low: 0.79,
  ci_high: 0.94,
  ci_method: "hksj",
  estimate_log: -0.15,
  se_log: 0.04,
  tau2: 0.004,
  i2: 45,
  q: 12,
  q_p: 0.08,
  prediction_low: 0.7,
  prediction_high: 1.05,
  studies: [
    { study_id: "LEADER", label: "LEADER", yi: -0.14, vi: 0.003, effect: 0.87, ci_low: 0.78, ci_high: 0.97, weight: 55 },
    { study_id: "SUSTAIN-6", label: "SUSTAIN-6", yi: -0.3, vi: 0.02, effect: 0.74, ci_low: 0.58, ci_high: 0.95, weight: 45 },
  ],
  notes: [],
};

describe("ForestPlot", () => {
  it("renders a labelled row per study plus the pooled estimate", () => {
    const { container, getByText } = render(<ForestPlot pool={pool} />);
    expect(getByText("LEADER")).toBeInTheDocument();
    expect(getByText("SUSTAIN-6")).toBeInTheDocument();
    expect(getByText("Pooled (RE)")).toBeInTheDocument();
    // One row line + CI whiskers; pooled diamond is a polygon.
    expect(container.querySelector("polygon")).toBeInTheDocument();
    expect(container.querySelectorAll("rect").length).toBe(2);
  });
});
