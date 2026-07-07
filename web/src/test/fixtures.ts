import type { ReviewResult, ReviewSummary } from "../lib/types";

export const reviewFixture: ReviewResult = {
  question: {
    id: "glp1-mace",
    text: "Do GLP-1 receptor agonists reduce MACE versus placebo?",
    pico: {
      population: "Adults with type 2 diabetes",
      intervention: "GLP-1 receptor agonist",
      comparator: "Placebo",
      outcome: "3-point MACE",
    },
    measure: "HR",
    trial_ids: ["NCT01179048", "NCT01720446", "NCT00000009"],
  },
  extractions: [
    {
      study_id: "NCT01179048",
      label: "LEADER",
      measure: "HR",
      hr: 0.87,
      ci_low: 0.78,
      ci_high: 0.97,
      flagged: false,
      flag_reason: null,
      confirmed: false,
      provenance: [
        {
          trial_id: "NCT01179048",
          snippet: "Primary outcome: HR 0.87 (0.78-0.97)",
          source_url: "https://clinicaltrials.gov/study/NCT01179048",
          field: "outcomeMeasures.analyses.paramValue",
        },
      ],
    },
    {
      study_id: "NCT01720446",
      label: "SUSTAIN-6",
      measure: "HR",
      hr: 0.74,
      ci_low: 0.58,
      ci_high: 0.95,
      flagged: false,
      flag_reason: null,
      confirmed: false,
      provenance: [
        {
          trial_id: "NCT01720446",
          snippet: "Primary outcome: HR 0.74 (0.58-0.95)",
          source_url: "https://clinicaltrials.gov/study/NCT01720446",
          field: "outcomeMeasures.analyses.paramValue",
        },
      ],
    },
    {
      study_id: "NCT00000009",
      label: "CURVE-ONLY",
      measure: "HR",
      hr: null,
      ci_low: null,
      ci_high: null,
      flagged: true,
      flag_reason: "No hazard-ratio analysis found in structured results.",
      confirmed: false,
      provenance: [
        { trial_id: "NCT00000009", snippet: "", source_url: null, field: null },
      ],
    },
  ],
  validations: [
    { study_id: "NCT01179048", passed: true, issues: [] },
    { study_id: "NCT01720446", passed: true, issues: [] },
    {
      study_id: "NCT00000009",
      passed: false,
      issues: [
        {
          study_id: "NCT00000009",
          code: "not_extracted",
          message: "No usable effect estimate extracted.",
        },
      ],
    },
  ],
  pool: {
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
      { study_id: "NCT01179048", label: "LEADER", yi: -0.14, vi: 0.003, effect: 0.87, ci_low: 0.78, ci_high: 0.97, weight: 55 },
      { study_id: "NCT01720446", label: "SUSTAIN-6", yi: -0.3, vi: 0.02, effect: 0.74, ci_low: 0.58, ci_high: 0.95, weight: 45 },
    ],
    notes: [],
  },
  summary:
    "Pooling 2 trials, GLP-1 receptor agonist reduced 3-point MACE versus Placebo, with a statistically significant effect: HR 0.86 (95% CI 0.79-0.94, Hartung-Knapp).",
};

export const summariesFixture: ReviewSummary[] = [
  {
    question_id: "glp1-mace",
    text: "Do GLP-1 receptor agonists reduce MACE versus placebo?",
    versions: 1,
    k: 8,
    estimate: 0.86,
    ci_low: 0.79,
    ci_high: 0.94,
    measure: "HR",
    status: "unchanged",
  },
];
