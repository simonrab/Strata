import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { PrismaFlowView } from "./PrismaFlow";
import type { PrismaFlow } from "../lib/types";

const flow: PrismaFlow = {
  identified: 10,
  identified_by_source: { "ClinicalTrials.gov": 8, "Europe PMC": 2 },
  duplicates_removed: 1,
  screened: 9,
  not_retrieved: 1,
  assessed: 8,
  excluded: [
    { reason: "No extractable effect data reported", count: 2, study_ids: ["NCT7", "NCT8"] },
    { reason: "Confidence interval does not bracket the estimate", count: 1, study_ids: ["NCT9"] },
  ],
  included: 5,
  included_in_synthesis: 5,
  synthesis_note: "",
};

describe("PrismaFlowView", () => {
  it("renders every stage count and the source breakdown", () => {
    const { getByText } = render(<PrismaFlowView flow={flow} />);
    expect(getByText("Records identified")).toBeInTheDocument();
    expect(getByText("Records screened")).toBeInTheDocument();
    expect(getByText("Reports assessed for eligibility")).toBeInTheDocument();
    expect(getByText("Studies included in synthesis (meta-analysis)")).toBeInTheDocument();
    // Source line combines the per-source counts.
    expect(getByText("8 ClinicalTrials.gov · 2 Europe PMC")).toBeInTheDocument();
  });

  it("shows removed branches with their reasons and counts", () => {
    const { getByText } = render(<PrismaFlowView flow={flow} />);
    expect(getByText("Duplicates removed")).toBeInTheDocument();
    expect(getByText("Reports not retrieved")).toBeInTheDocument();
    expect(getByText("Records excluded")).toBeInTheDocument();
    expect(getByText("No extractable effect data reported")).toBeInTheDocument();
    expect(getByText("Confidence interval does not bracket the estimate")).toBeInTheDocument();
  });

  it("surfaces the synthesis note when the pool was withheld", () => {
    const withheld: PrismaFlow = {
      ...flow,
      included_in_synthesis: 0,
      synthesis_note: "Pooling withheld pending homogeneity confirmation.",
    };
    const { getByText } = render(<PrismaFlowView flow={withheld} />);
    expect(
      getByText("Pooling withheld pending homogeneity confirmation.")
    ).toBeInTheDocument();
  });

  it("omits a removed branch that has no records", () => {
    const clean: PrismaFlow = {
      ...flow,
      duplicates_removed: 0,
      not_retrieved: 0,
      excluded: [],
    };
    const { queryByText } = render(<PrismaFlowView flow={clean} />);
    expect(queryByText("Duplicates removed")).toBeNull();
    expect(queryByText("Reports not retrieved")).toBeNull();
    expect(queryByText("Records excluded")).toBeNull();
  });
});
