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

export interface Assumption {
  code: string;
  detail: string;
  study_id?: string | null;
}

export interface BinaryArm {
  events: number;
  total: number;
  reported_pct?: number | null;
}

export interface BinaryEffect {
  study_id: string;
  label: string;
  treatment: BinaryArm;
  control: BinaryArm;
  provenance: Provenance[];
}

export interface ContinuousArm {
  mean: number;
  sd: number;
  n: number;
}

export interface ContinuousEffect {
  study_id: string;
  label: string;
  treatment: ContinuousArm;
  control: ContinuousArm;
  provenance: Provenance[];
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
  assumptions?: Assumption[];
}

// Ratio measures pool on the log scale (null effect = 1); MD/SMD are natural
// (null effect = 0). Mirrors livemeta.core.schema.RATIO_MEASURES.
export const RATIO_MEASURES = ["RR", "OR", "HR"];

export function isRatioMeasure(measure: string): boolean {
  return RATIO_MEASURES.includes(measure);
}

export function nullEffect(measure: string): number {
  return isRatioMeasure(measure) ? 1 : 0;
}

// Whether a CI excludes the null effect for this measure.
export function excludesNull(measure: string, ciLow: number, ciHigh: number): boolean {
  const n = nullEffect(measure);
  return ciHigh < n || ciLow > n;
}

export interface TrialExtraction {
  study_id: string;
  label: string;
  measure: string;
  // Clinical endpoint the effect measures, and the arms CT.gov compared (in its
  // listed order; surfaced for human verification, not read as orientation).
  endpoint?: string | null;
  comparison_arms?: string[];
  hr: number | null;
  ci_low: number | null;
  ci_high: number | null;
  binary?: BinaryEffect | null;
  continuous?: ContinuousEffect | null;
  flagged: boolean;
  flag_reason: string | null;
  confirmed: boolean;
  provenance: Provenance[];
  assumptions?: Assumption[];
}

// A compact effect string per extraction variant, matching the backend's
// _effect_summary: ratio → "0.86 [0.79, 0.94]"; binary → "12/500 vs 20/500";
// continuous → the point estimate.
export function formatEffect(e: TrialExtraction): string | null {
  if (e.binary) {
    const { treatment: t, control: c } = e.binary;
    return `${t.events}/${t.total} vs ${c.events}/${c.total}`;
  }
  if (e.continuous) {
    const { treatment: t, control: c } = e.continuous;
    return `${t.mean} vs ${c.mean}`;
  }
  if (e.hr != null) {
    return `${e.hr.toFixed(2)} [${e.ci_low?.toFixed(2)}, ${e.ci_high?.toFixed(2)}]`;
  }
  return null;
}

export interface ReviewDecision {
  study_id: string;
  decision: "confirmed" | "flagged";
  reason?: string | null;
  timestamp?: string | null;
}

// livemeta.core.schema.EligibilityDecision — one candidate's search -> screen ->
// include call. `by_claude` is false when the clinical read didn't run (keyless
// or failed): the trial was auto-included in reduced mode, never silently.
export interface EligibilityDecision {
  study_id: string;
  decision: "included" | "excluded";
  reason: string;
  domain?: string | null;
  quote?: Provenance | null;
  by_claude: boolean;
  confirmed: boolean;
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

export interface EggerResult {
  k: number;
  intercept: number | null;
  se_intercept: number | null;
  t: number | null;
  p: number | null;
  applicable: boolean;
}

export interface GradeAssessment {
  outcome: string;
  starting_level: GradeRating;
  certainty: GradeRating;
  domains: GradeDomain[];
  sof_line: string;
  footnotes: string[];
  publication_bias_test?: EggerResult | null;
}

export interface DiversityDomain {
  key: string;
  judgment: "similar" | "mixed" | "divergent" | "not_assessed";
  rationale: string;
  by_claude: boolean;
}

export interface DiversityAssessment {
  domains: DiversityDomain[];
  i2: number | null;
  i2_band: string;
  requires_confirmation: boolean;
  confirmed: boolean;
  // False when the clinical read didn't run (no model key): the gate rested on
  // the I² band alone, and the UI should show that reduced coverage honestly.
  clinical_assessed?: boolean;
  rationale: string;
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

// livemeta.core.schema.TrialCandidate — a trial surfaced by search, before
// extraction (used by the on-demand living "check for new trials").
export interface TrialCandidate {
  nct_id: string;
  title: string;
  source?: string;
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

export interface PrismaExclusion {
  reason: string;
  count: number;
  study_ids: string[];
  // "screening" = a clinical PICO/design eligibility call; "reports" = cleared
  // screening but had no extractable/valid effect data.
  stage?: "screening" | "reports";
}

// PRISMA 2020 record-flow, derived deterministically from the run. Mirrors
// livemeta.core.schema.PrismaFlow. Reconciles: identified = screened +
// duplicates_removed; screened = assessed + not_retrieved; assessed = included +
// sum(excluded counts).
export interface PrismaFlow {
  identified: number;
  identified_by_source: Record<string, number>;
  duplicates_removed: number;
  screened: number;
  not_retrieved: number;
  assessed: number;
  excluded: PrismaExclusion[];
  included: number;
  included_in_synthesis: number;
  synthesis_note: string;
}

export interface ReviewResult {
  question: Question;
  screening?: EligibilityDecision[];
  extractions: TrialExtraction[];
  validations: ValidationResult[];
  pool: PoolResult | null;
  summary: string;
  rob: RobAssessment[];
  grade: GradeAssessment | null;
  sensitivity: LeaveOneOutRow[];
  diversity?: DiversityAssessment | null;
  prisma?: PrismaFlow | null;
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

// --- Competitive-intelligence landscape (mirrors livemeta.core.ci.schema) ----

export type Phase =
  | "preclinical"
  | "phase_1"
  | "phase_1_2"
  | "phase_2"
  | "phase_2_3"
  | "phase_3"
  | "phase_4"
  | "filed"
  | "approved"
  | "withdrawn"
  | "unknown";

// Short display labels for each stage, in ascending order of advancement.
export const PHASE_LABEL: Record<Phase, string> = {
  preclinical: "Preclinical",
  phase_1: "Phase 1",
  phase_1_2: "Phase 1/2",
  phase_2: "Phase 2",
  phase_2_3: "Phase 2/3",
  phase_3: "Phase 3",
  phase_4: "Phase 4",
  filed: "Filed",
  approved: "Approved",
  withdrawn: "Withdrawn",
  unknown: "Unknown",
};

export interface DevelopmentEvent {
  asset_name: string;
  indication: string;
  line_of_therapy?: string | null;
  phase: Phase;
  status?: string | null;
  event_type: string;
  date?: string | null;
  source_type: string;
  sponsor?: string | null;
  sponsor_class?: string | null;
  provenance: Provenance[];
}

export interface EvidenceBadge {
  question_id: string;
  measure: string;
  state: "pooled" | "gate_open" | "abstained";
  estimate?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  grade_certainty?: string | null;
  conclusion?: string | null;
  version?: number | null;
  k: number;
}

export interface LandscapeCell {
  asset_name: string;
  indication: string;
  line_of_therapy?: string | null;
  current_phase: Phase;
  status?: string | null;
  sponsor?: string | null;
  sponsor_class?: string | null;
  latest_event?: DevelopmentEvent | null;
  conflict: boolean;
  conflict_note?: string | null;
  question_id?: string | null;
  evidence?: EvidenceBadge | null;
  provenance: Provenance[];
}

export interface Landscape {
  condition: string;
  as_of?: string | null;
  assets: string[];
  indications: string[];
  cells: LandscapeCell[];
  notes: string[];
}

// A company's entire pipeline across every indication (mirrors CompanyPipeline
// in livemeta.core.ci.schema). Reuses LandscapeCell so the board renders
// identically, and adds the sponsor's FDA approvals.
export interface CompanyPipeline {
  sponsor: string;
  as_of?: string | null;
  assets: string[];
  indications: string[];
  cells: LandscapeCell[];
  approvals: RegulatoryApproval[];
  notes: string[];
}

// --- v2: source selection, asset dossiers, indication mapping ----------------

export type Source = "ctgov" | "pubmed" | "openfda" | "announcement" | "filing";

// The structured sources shown in the picker. ClinicalTrials.gov is always on;
// PubMed (Europe PMC) and openFDA are available but opt-in — see DEFAULT_SOURCES.
export const STRUCTURED_SOURCES: Source[] = ["ctgov", "pubmed", "openfda"];
export const FREE_TEXT_SOURCES: Source[] = ["announcement", "filing"];

// The default selection: ClinicalTrials.gov only. PubMed and openFDA start off
// and are opted into per request (the backend provisions their clients only when
// they are named), so a run never silently pulls in unpooled or regulatory data.
export const DEFAULT_SOURCES: Source[] = ["ctgov"];

export const SOURCE_LABEL: Record<Source, string> = {
  ctgov: "ClinicalTrials.gov",
  pubmed: "PubMed / Europe PMC",
  openfda: "openFDA (US FDA approvals)",
  announcement: "Announcements",
  filing: "Filings",
};

export interface SubPopulation {
  base_indication: string;
  age_min?: number | null;
  age_max?: number | null;
  sex?: string | null;
  comorbidities: string[];
  line_of_therapy?: string | null;
  prior_treatment?: string | null;
  label: string;
  provenance: Provenance[];
}

export interface TrialDetail {
  nct_id: string;
  title: string;
  asset_name: string;
  phase: Phase;
  status?: string | null;
  enrollment?: number | null;
  start_date?: string | null;
  primary_completion_date?: string | null;
  results_posted_date?: string | null;
  has_results: boolean;
  sponsor?: string | null;
  sponsor_class?: string | null;
  countries: string[];
  indication: string;
  sub_population?: SubPopulation | null;
  effect?: TrialExtraction | null;
  provenance: Provenance[];
}

export interface RegulatoryApproval {
  drug: string;
  sponsor?: string | null;
  application_number: string;
  brand_names: string[];
  approval_date?: string | null;
  marketing_status?: string | null;
  indication_approx?: string | null;
  provenance: Provenance[];
}

export interface CountryCount {
  country: string;
  trials: number;
}

export interface SubIndicationGroup {
  signature: string;
  label: string;
  trial_ids: string[];
  phases: string[];
  evidence?: EvidenceBadge | null;
}

export interface Asset {
  name: string;
  aliases: string[];
  sponsor?: string | null;
  sponsor_class?: string | null;
  drug_class?: string | null;
  provenance: Provenance[];
}

export interface AssetDossier {
  asset: Asset;
  sources: Source[];
  trials: TrialDetail[];
  countries: CountryCount[];
  events: DevelopmentEvent[];
  readouts: TrialDetail[];
  approvals: RegulatoryApproval[];
  sub_indications: SubIndicationGroup[];
  notes: string[];
}

export interface IndicationNode {
  signature: string;
  label: string;
  sub_population?: SubPopulation | null;
  assets: string[];
  trial_count: number;
  stage_distribution: Record<string, number>;
  countries: CountryCount[];
  approvals: RegulatoryApproval[];
  evidence?: EvidenceBadge | null;
}

export interface IndicationMap {
  indication: string;
  sources: Source[];
  nodes: IndicationNode[];
  notes: string[];
}

// --- v3: market intelligence — change-feed, radar, compare, MoA, chat --------

export type ChangeType =
  | "new_program"
  | "advanced"
  | "readout"
  | "setback"
  | "evidence_moved"
  | "conflict_opened";

export interface LandscapeChange {
  asset_name: string;
  indication: string;
  change_type: ChangeType;
  date?: string | null;
  from_phase?: Phase | null;
  to_phase?: Phase | null;
  summary: string;
  estimate_prev?: number | null;
  estimate_curr?: number | null;
  provenance: Provenance[];
}

export interface LandscapeDiff {
  condition: string;
  since?: string | null;
  until?: string | null;
  changes: LandscapeChange[];
  notes: string[];
}

export type MilestoneKind = "expected_readout" | "pdufa";

export interface Milestone {
  asset_name: string;
  indication: string;
  nct_id: string;
  title: string;
  phase: Phase;
  kind: MilestoneKind;
  expected_date: string;
  quarter: string;
  sponsor?: string | null;
  provenance: Provenance[];
}

export interface MilestoneRadar {
  scope: string;
  as_of?: string | null;
  horizon_months: number;
  milestones: Milestone[];
  notes: string[];
}

export interface ComparisonRow {
  label: string;
  values: string[];
  more: boolean[];
}

export interface AssetEvidenceContext {
  asset_name: string;
  indication: string;
  population: string;
  comparator?: string | null;
  plain_summary: string;
  badge?: EvidenceBadge | null;
}

export interface Comparability {
  directly_comparable: boolean;
  reasons: string[];
}

export interface AssetComparison {
  assets: string[];
  indication?: string | null;
  rows: ComparisonRow[];
  evidence: AssetEvidenceContext[];
  comparability: Comparability;
  notes: string[];
}

export interface MoaCluster {
  drug_class: string;
  label: string;
  assets: string[];
  program_count: number;
  stage_distribution: Record<string, number>;
  plain_summary: string;
  evidence?: EvidenceBadge | null;
}

export interface MoaLandscape {
  condition: string;
  clusters: MoaCluster[];
  notes: string[];
}

export interface MarketQuery {
  tool: string;
  condition?: string | null;
  assets: string[];
  indication?: string | null;
  sponsor?: string | null;
  since?: string | null;
  until?: string | null;
  as_of?: string | null;
  horizon_months?: number | null;
  confidence: string;
  reason: string;
}

// The routed payload is one of the view models above, keyed by `tool`.
export interface MarketAnswer {
  text: string;
  intent: MarketQuery;
  tool: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  result: any;
  narrative: string;
  suggestions: string[];
  notes: string[];
}
