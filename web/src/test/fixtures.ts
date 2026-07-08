import type {
  ReviewDiff,
  ReviewResult,
  ReviewSummary,
  SnapshotMeta,
} from "../lib/types";

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
      { study_id: "NCT01179048", label: "LEADER", yi: -0.14, vi: 0.003, effect: 0.87, ci_low: 0.78, ci_high: 0.97, weight: 55 },
      { study_id: "NCT01720446", label: "SUSTAIN-6", yi: -0.3, vi: 0.02, effect: 0.74, ci_low: 0.58, ci_high: 0.95, weight: 45 },
    ],
    notes: [],
  },
  summary:
    "Pooling 2 trials, GLP-1 receptor agonist reduced 3-point MACE versus Placebo, with a statistically significant effect: HR 0.86 (95% CI 0.79-0.94, Hartung-Knapp).",
  rob: [
    {
      study_id: "NCT01179048",
      label: "LEADER",
      overall: "some_concerns",
      confirmed: false,
      domains: [
        { key: "D1", name: "Randomization process", judgment: "low", rationale: "Central randomization with concealed allocation.", source_quote: { trial_id: "NCT01179048", snippet: "Participants were randomly assigned via a centralized, computer-generated schedule.", source_url: null, field: "rob.D1" }, confirmed: false },
        { key: "D2", name: "Deviations from intended interventions", judgment: "some_concerns", rationale: "Minor protocol deviations, ITT retained.", source_quote: { trial_id: "NCT01179048", snippet: "Three patients received non-protocol therapy; retained in ITT.", source_url: null, field: "rob.D2" }, confirmed: false },
        { key: "D3", name: "Missing outcome data", judgment: "low", rationale: "Attrition balanced and low.", source_quote: { trial_id: "NCT01179048", snippet: "Loss to follow-up was 4.2% overall.", source_url: null, field: "rob.D3" }, confirmed: false },
        { key: "D4", name: "Measurement of the outcome", judgment: "low", rationale: "Blinded adjudication of the outcome.", source_quote: { trial_id: "NCT01179048", snippet: "Events adjudicated by a masked committee.", source_url: null, field: "rob.D4" }, confirmed: false },
        { key: "D5", name: "Selection of the reported result", judgment: "low", rationale: "Pre-registered primary endpoint.", source_quote: { trial_id: "NCT01179048", snippet: "Analysis followed the pre-specified protocol.", source_url: null, field: "rob.D5" }, confirmed: false },
      ],
    },
    {
      study_id: "NCT01720446",
      label: "SUSTAIN-6",
      overall: "low",
      confirmed: false,
      domains: [
        { key: "D1", name: "Randomization process", judgment: "low", rationale: "Adequate randomization.", source_quote: { trial_id: "NCT01720446", snippet: "Randomized 1:1 with concealed allocation.", source_url: null, field: "rob.D1" }, confirmed: false },
        { key: "D2", name: "Deviations from intended interventions", judgment: "low", rationale: "ITT analysis.", source_quote: { trial_id: "NCT01720446", snippet: "Primary analysis was intention-to-treat.", source_url: null, field: "rob.D2" }, confirmed: false },
        { key: "D3", name: "Missing outcome data", judgment: "low", rationale: "Complete follow-up.", source_quote: { trial_id: "NCT01720446", snippet: "Vital status known for 99.6%.", source_url: null, field: "rob.D3" }, confirmed: false },
        { key: "D4", name: "Measurement of the outcome", judgment: "low", rationale: "Blinded adjudication.", source_quote: { trial_id: "NCT01720446", snippet: "Independent adjudication committee.", source_url: null, field: "rob.D4" }, confirmed: false },
        { key: "D5", name: "Selection of the reported result", judgment: "low", rationale: "Pre-specified endpoint.", source_quote: { trial_id: "NCT01720446", snippet: "Reported the pre-registered primary outcome.", source_url: null, field: "rob.D5" }, confirmed: false },
      ],
    },
  ],
  grade: {
    outcome: "3-point MACE",
    starting_level: "high",
    certainty: "moderate",
    sof_line:
      "GLP-1 receptor agonist reduced 3-point MACE (HR 0.86, 95% CI 0.79-0.94; 2 trials); moderate-certainty evidence.",
    domains: [
      { name: "risk_of_bias", serious: "not_serious", downgrade: 0, rationale: "Included trials are at low risk of bias across RoB 2 domains.", by_claude: false },
      { name: "inconsistency", serious: "not_serious", downgrade: 0, rationale: "Heterogeneity was moderate (I² = 45%). Estimates are consistent.", by_claude: false },
      { name: "indirectness", serious: "serious", downgrade: -1, rationale: "Baseline NYHA class differs from the target population.", by_claude: true },
      { name: "imprecision", serious: "not_serious", downgrade: 0, rationale: "The 95% CI excludes no effect and is reasonably narrow.", by_claude: false },
      { name: "publication_bias", serious: "not_serious", downgrade: 0, rationale: "Funnel plot symmetric.", by_claude: true },
    ],
    footnotes: [
      "Downgraded for indirectness: Baseline NYHA class differs from the target population.",
    ],
  },
  sensitivity: [
    { omitted_study_id: "NCT01179048", omitted_label: "LEADER", k: 1, estimate: 0.82, ci_low: 0.7, ci_high: 0.96, i2: 0 },
    { omitted_study_id: "NCT01720446", omitted_label: "SUSTAIN-6", k: 1, estimate: 0.88, ci_low: 0.8, ci_high: 0.97, i2: 0 },
  ],
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

// A living update: the 7-trial baseline (v1) grew to 8 when AMPLITUDE-O landed.
// The estimate refined but the benefit still holds (conclusion unchanged).
export const diffFixture: ReviewDiff = {
  question_id: "glp1-mace",
  previous_version: 1,
  current_version: 2,
  estimate_prev: 0.88,
  estimate_curr: 0.86,
  delta: -0.02,
  ci_prev: [0.81, 0.96],
  ci_curr: [0.79, 0.94],
  k_prev: 7,
  k_curr: 8,
  added_trials: ["NCT03496298"],
  significance_changed: false,
  direction_changed: false,
  conclusion_changed: false,
  notes: [],
};

export const historyFixture: SnapshotMeta[] = [
  {
    question_id: "glp1-mace",
    version: 1,
    created_at: "2026-07-08T09:00:00+00:00",
    k: 7,
    estimate: 0.88,
    ci_low: 0.81,
    ci_high: 0.96,
    measure: "HR",
  },
  {
    question_id: "glp1-mace",
    version: 2,
    created_at: "2026-07-08T10:30:00+00:00",
    k: 8,
    estimate: 0.86,
    ci_low: 0.79,
    ci_high: 0.94,
    measure: "HR",
  },
];
