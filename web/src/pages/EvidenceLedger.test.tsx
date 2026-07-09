import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { EvidenceLedger } from "./EvidenceLedger";
import { reviewFixture } from "../test/fixtures";
import type { ReviewResult } from "../lib/types";

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

  it("renders a continuous (MD) review with events-free effect cells and header", async () => {
    const md: ReviewResult = {
      ...reviewFixture,
      question: {
        ...reviewFixture.question,
        measure: "MD",
        trial_ids: ["NCT20000001"],
      },
      extractions: [
        {
          study_id: "NCT20000001",
          label: "TrialX",
          measure: "MD",
          hr: null,
          ci_low: null,
          ci_high: null,
          continuous: {
            study_id: "NCT20000001",
            label: "TrialX",
            treatment: { mean: 10, sd: 2, n: 50 },
            control: { mean: 8, sd: 2.5, n: 50 },
            provenance: [],
          },
          flagged: false,
          flag_reason: null,
          confirmed: false,
          provenance: [
            { trial_id: "NCT20000001", snippet: "10±2 vs 8±2.5", source_url: null, field: null },
          ],
        },
      ],
    };
    vi.mocked(getReview).mockResolvedValue(md);
    renderAt("q-md");

    expect(await screen.findByText("TrialX")).toBeInTheDocument();
    // Header reflects the measure, not "HR".
    expect(screen.getByText("Effect (MD)")).toBeInTheDocument();
    // The continuous effect shows the arm means, no HR bracket.
    expect(screen.getByText("10 vs 8")).toBeInTheDocument();
  });

  it("shows the homogeneity gate when a review is withheld for confirmation", async () => {
    const gated: ReviewResult = {
      ...reviewFixture,
      pool: null,
      diversity: {
        domains: [
          { key: "population", judgment: "divergent", rationale: "differs", by_claude: true },
          { key: "intervention", judgment: "similar", rationale: "", by_claude: true },
          { key: "comparator", judgment: "similar", rationale: "", by_claude: true },
          { key: "outcome", judgment: "mixed", rationale: "", by_claude: true },
        ],
        i2: 82,
        i2_band: "substantial",
        requires_confirmation: true,
        confirmed: false,
        rationale: "Pooling withheld because heterogeneity is substantial.",
      },
    };
    vi.mocked(getReview).mockResolvedValue(gated);
    renderAt("glp1-mace");

    expect(
      await screen.findByText(/confirm the trials are combinable/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Confirm and pool unlike trials/i })
    ).toBeInTheDocument();
    // The I² band is surfaced.
    expect(screen.getByText(/I² 82% \(substantial\)/)).toBeInTheDocument();
  });
});
