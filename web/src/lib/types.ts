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
  provenance: Provenance[];
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
}

export interface PipelineEvent {
  stage: string;
  message: string;
  data: unknown;
}
