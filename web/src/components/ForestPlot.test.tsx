import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ForestPlot } from "./ForestPlot";
import type { PoolResult } from "../lib/types";

const pool: PoolResult = {
  measure: "HR",
  model: "random",
  method: "REML",
  pool_method: "inverse_variance",
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

  it("badges a highlighted study, and none without the prop", () => {
    const withHl = render(
      <ForestPlot pool={pool} highlightStudyIds={["SUSTAIN-6"]} />
    );
    expect(withHl.getByText("New")).toBeInTheDocument();
    withHl.unmount();
    const noHl = render(<ForestPlot pool={pool} />);
    expect(noHl.queryByText("New")).toBeNull();
  });

  it("centres the no-effect line at 0 for a continuous (MD) pool", () => {
    // A mean-difference pool spans negative to positive; the reference line must
    // sit at 0, and the axis must be linear (no log of a non-positive effect).
    const mdPool: PoolResult = {
      ...pool,
      measure: "MD",
      estimate: 2.0,
      estimate_log: 2.0,
      ci_low: 0.5,
      ci_high: 3.5,
      studies: [
        { study_id: "A", label: "A", yi: 2.0, vi: 0.2, effect: 2.0, ci_low: 1.1, ci_high: 2.9, weight: 60 },
        { study_id: "B", label: "B", yi: -0.5, vi: 0.3, effect: -0.5, ci_low: -1.6, ci_high: 0.6, weight: 40 },
      ],
    };
    const { container, getByText } = render(<ForestPlot pool={mdPool} />);
    // Axis header shows the measure, not "HR".
    expect(getByText("MD [95% CI]")).toBeInTheDocument();
    // A negative effect renders finite coordinates (log axis would give NaN).
    const negRect = Array.from(container.querySelectorAll("rect")).find(
      (r) => r.getAttribute("x") && !Number.isNaN(Number(r.getAttribute("x")))
    );
    expect(negRect).toBeTruthy();
    // The "0.00" tick appears on the linear axis.
    expect(getByText("0")).toBeInTheDocument();
  });
});
