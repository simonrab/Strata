// Mirrors livemeta.core.schema (kept in sync by hand for Slice 1).

export interface Provenance {
  trial_id: string;
  snippet: string;
  source_url?: string | null;
  field?: string | null;
}

export interface StudyResult {
  study_id: string;
  label: string;
  yi: number;
  vi: number;
  effect: number;
  ci_low: number;
  ci_high: number;
  weight: number;
}

export interface PoolResult {
  measure: string;
  model: string;
  method: string;
  pool_method: string;
  engine: string;
  k: number;
  estimate: number;
  ci_low: number;
  ci_high: number;
  ci_method: string;
  estimate_log: number;
  se_log: number;
  tau2: number;
  i2: number;
  q: number;
  q_p: number;
  prediction_low: number | null;
  prediction_high: number | null;
  studies: StudyResult[];
  notes: string[];
}

export interface TrialExtraction {
  study_id: string;
  label: string;
  measure: string;
  hr: number | null;
  ci_low: number | null;
  ci_high: number | null;
  flagged: boolean;
  flag_reason: string | null;
  confirmed: boolean;
  provenance: Provenance[];
}

export interface ReviewDecision {
  study_id: string;
  decision: "confirmed" | "flagged";
  reason?: string | null;
  timestamp?: string | null;
}

export type RobJudgment = "low" | "some_concerns" | "high" | "pending";

export interface RobDomain {
  key: string;
  name: string;
  judgment: RobJudgment;
  rationale: string;
  source_quote: Provenance | null;
  confirmed: boolean;
}

export interface RobAssessment {
  study_id: string;
  label: string;
  domains: RobDomain[];
  overall: RobJudgment;
  confirmed: boolean;
}

export type GradeRating = "high" | "moderate" | "low" | "very_low";

export interface GradeDomain {
  name: string;
  serious: "not_serious" | "serious" | "very_serious";
  downgrade: number;
  rationale: string;
  by_claude: boolean;
}

export interface GradeAssessment {
  outcome: string;
  starting_level: GradeRating;
  certainty: GradeRating;
  domains: GradeDomain[];
  sof_line: string;
  footnotes: string[];
}

export interface LeaveOneOutRow {
  omitted_study_id: string;
  omitted_label: string;
  k: number;
  estimate: number;
  ci_low: number;
  ci_high: number;
  i2: number;
}

export interface ReviewSummary {
  question_id: string;
  text: string;
  versions: number;
  k: number;
  estimate: number | null;
  ci_low: number | null;
  ci_high: number | null;
  measure: string;
  status: string;
}

export interface PICO {
  population: string;
  intervention: string;
  comparator: string;
  outcome: string;
}

export interface Question {
  id: string;
  text: string;
  pico: PICO;
  measure: string;
  trial_ids: string[];
}

export interface ValidationResult {
  study_id: string;
  passed: boolean;
  issues: { study_id: string; code: string; message: string }[];
}

export interface ReviewResult {
  question: Question;
  extractions: TrialExtraction[];
  validations: ValidationResult[];
  pool: PoolResult | null;
  summary: string;
  rob: RobAssessment[];
  grade: GradeAssessment | null;
  sensitivity: LeaveOneOutRow[];
}

export interface PipelineEvent {
  stage: string;
  message: string;
  data: unknown;
}

export interface ReviewDiff {
  question_id: string;
  previous_version: number;
  current_version: number;
  estimate_prev: number | null;
  estimate_curr: number | null;
  delta: number | null;
  ci_prev: [number, number] | null;
  ci_curr: [number, number] | null;
  k_prev: number;
  k_curr: number;
  added_trials: string[];
  significance_changed: boolean;
  direction_changed: boolean;
  conclusion_changed: boolean;
  notes: string[];
}

export interface SnapshotMeta {
  question_id: string;
  version: number;
  created_at: string;
  k: number;
  estimate: number | null;
  ci_low: number | null;
  ci_high: number | null;
  measure: string;
}
