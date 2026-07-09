import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { FunnelPlot } from "./FunnelPlot";
import type { EggerResult, PoolResult, StudyResult } from "../lib/types";

function studies(n: number): StudyResult[] {
  return Array.from({ length: n }, (_, i) => {
    const vi = 0.01 + 0.05 * i;
    const yi = -0.15 + (i % 2 ? 0.05 : -0.05);
    return {
      study_id: `S${i}`,
      label: `S${i}`,
      yi,
      vi,
      effect: Math.exp(yi),
      ci_low: Math.exp(yi - 1.96 * Math.sqrt(vi)),
      ci_high: Math.exp(yi + 1.96 * Math.sqrt(vi)),
      weight: 100 / n,
    };
  });
}

const pool: PoolResult = {
  measure: "HR",
  model: "random",
  method: "REML",
  pool_method: "inverse_variance",
  engine: "python",
  k: 10,
  estimate: 0.86,
  ci_low: 0.79,
  ci_high: 0.94,
  ci_method: "hksj",
  estimate_log: -0.15,
  se_log: 0.04,
  tau2: 0.004,
  i2: 30,
  q: 10,
  q_p: 0.3,
  prediction_low: null,
  prediction_high: null,
  studies: studies(10),
  notes: [],
};

const egger: EggerResult = {
  k: 10,
  intercept: 0.42,
  se_intercept: 0.3,
  t: 1.4,
  p: 0.19,
  applicable: true,
};

describe("FunnelPlot", () => {
  it("renders one point per study and the Egger summary", () => {
    const { container, getByText } = render(<FunnelPlot pool={pool} egger={egger} />);
    expect(container.querySelectorAll("circle").length).toBe(10);
    // The pseudo-95% confidence funnel is a dashed triangle.
    expect(container.querySelector("polygon")).toBeInTheDocument();
    // The Egger result is surfaced with its p-value.
    expect(getByText(/Egger's test \(10 studies\)/)).toBeInTheDocument();
    expect(getByText(/p = 0.190/)).toBeInTheDocument();
  });
});
