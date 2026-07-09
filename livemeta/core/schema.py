"""Pydantic schema for the meta-analysis pipeline.

Every extracted value carries provenance; every pooled result is fully
described so the UI and the audit trail can trace each number to its source.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EffectMeasure(str, Enum):
    RR = "RR"  # risk ratio
    OR = "OR"  # odds ratio
    HR = "HR"  # hazard ratio (time-to-event, generic inverse-variance)
    MD = "MD"  # mean difference (continuous, same scale)
    SMD = "SMD"  # standardized mean difference (continuous, differing scales)


# Ratio measures pool on the log scale; MD/SMD are already on the natural scale.
RATIO_MEASURES = {EffectMeasure.RR, EffectMeasure.OR, EffectMeasure.HR}


class PoolMethod(str, Enum):
    """How the per-study effects were combined.

    Inverse-variance is the default two-stage approach; Peto and Mantel-Haenszel
    are the rare-event alternatives Cochrane recommends when events are sparse.
    """

    IV = "inverse_variance"
    PETO = "peto"
    MANTEL_HAENSZEL = "mantel_haenszel"


class CIMethod(str, Enum):
    WALD = "wald"
    HKSJ = "hksj"  # Hartung-Knapp-Sidik-Jonkman (t-distribution)


class Provenance(BaseModel):
    """Where a value came from — trial ID plus the exact source snippet."""

    trial_id: str
    snippet: str
    source_url: str | None = None
    field: str | None = None


class Assumption(BaseModel):
    """A Cochrane data conversion the code ran, logged for the audit trail.

    Effect-size calculation sometimes has to convert reported statistics (a CI
    into a standard error, an SE into an SD, apply a small-sample correction).
    The conversions are standard Handbook formulas run in code — this records
    each one so a reviewer can see exactly which formula produced a pooled
    number, rather than trusting an opaque transform.
    """

    code: str  # e.g. "log_ratio_se_from_ci" | "smd_hedges_j" | "sd_from_se"
    detail: str  # human-readable, includes the applied formula
    study_id: str | None = None


class BinaryArm(BaseModel):
    events: int
    total: int
    reported_pct: float | None = None  # percentage as printed in the source, if any


class BinaryEffect(BaseModel):
    """A binary outcome for one trial: events/totals per arm, with provenance."""

    study_id: str
    label: str
    treatment: BinaryArm
    control: BinaryArm
    provenance: list[Provenance] = Field(default_factory=list)


class ContinuousArm(BaseModel):
    mean: float
    sd: float
    n: int


class ContinuousEffect(BaseModel):
    """A continuous outcome for one trial: mean/SD/n per arm, with provenance."""

    study_id: str
    label: str
    treatment: ContinuousArm
    control: ContinuousArm
    provenance: list[Provenance] = Field(default_factory=list)


class PICO(BaseModel):
    population: str
    intervention: str
    comparator: str
    outcome: str


class Question(BaseModel):
    id: str
    text: str
    pico: PICO
    measure: EffectMeasure = EffectMeasure.HR
    trial_ids: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    study_id: str
    code: str
    message: str


class ValidationResult(BaseModel):
    """Outcome of the deterministic gate for one trial."""

    study_id: str
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class EffectPoint(BaseModel):
    """A per-study effect on the analysis scale, ready to pool.

    `yi` is the effect (log scale for ratio measures), `vi` its variance. This is
    the common currency the stats engine pools, whether the point came from a
    2x2 table or a reported hazard ratio with its confidence interval.
    """

    study_id: str
    label: str
    yi: float
    vi: float
    provenance: list[Provenance] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class TrialExtraction(BaseModel):
    """A trial's extracted effect with provenance, or a flag for review.

    Measure-polymorphic: `hr/ci_low/ci_high` carry a ratio reported with a CI
    (the HR/RR/OR-as-ratio variant); `binary` carries a 2x2 table; `continuous`
    carries mean/SD/n per arm. Whichever variant applies, `point` is the common
    pooling currency the stats engine consumes. The ratio fields keep their
    historical names so existing snapshots and the frontend stay compatible.
    """

    study_id: str  # e.g. NCT id
    label: str
    measure: EffectMeasure = EffectMeasure.HR
    hr: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    binary: BinaryEffect | None = None  # 2x2 variant (RR/OR from event counts)
    continuous: ContinuousEffect | None = None  # mean/SD/n variant (MD/SMD)
    point: EffectPoint | None = None
    flagged: bool = False
    flag_reason: str | None = None
    confirmed: bool = False  # a human reviewer signed off on this extraction
    provenance: list[Provenance] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    """A human reviewer's confirm/flag call on one trial's extraction.

    The load-bearing human-in-the-loop record: a *flag* removes a trial from the
    pool; a *confirm* records sign-off for the audit trail. Every decision carries
    who-decided-what-when so the ledger is traceable end to end.
    """

    study_id: str
    decision: str  # "confirmed" | "flagged"
    reason: str | None = None
    timestamp: str | None = None


class DiversityDomain(BaseModel):
    """One PICO domain's clinical-diversity judgment across the pooled trials."""

    key: str  # population | intervention | comparator | outcome
    judgment: str = "not_assessed"  # similar | mixed | divergent | not_assessed
    rationale: str = ""
    by_claude: bool = True


class DiversityAssessment(BaseModel):
    """The homogeneity gate: is this set similar enough to pool?

    Combines Claude's clinical-diversity read across the four PICO domains with
    the deterministic statistical-heterogeneity band (I²). `requires_confirmation`
    is the load-bearing flag — when true, the pipeline withholds the pooled
    estimate until a human confirms the trials are clinically combinable.
    """

    domains: list[DiversityDomain] = Field(default_factory=list)
    i2: float | None = None
    i2_band: str = ""
    requires_confirmation: bool = False
    confirmed: bool = False
    rationale: str = ""


class DiversityDecision(BaseModel):
    """A human reviewer's sign-off that clinically diverse trials may be pooled."""

    decision: str = "confirmed"
    reason: str | None = None
    timestamp: str | None = None


class RobJudgment(str, Enum):
    """RoB 2 per-domain and overall judgment."""

    LOW = "low"  # +
    SOME_CONCERNS = "some_concerns"  # ?
    HIGH = "high"  # -
    PENDING = "pending"  # not yet assessed (e.g. no LLM key) — never fabricated


class RobDomain(BaseModel):
    """One RoB 2 domain: Claude's judgment with the source quote it rests on."""

    key: str  # D1..D5
    name: str
    judgment: RobJudgment = RobJudgment.PENDING
    rationale: str = ""
    source_quote: Provenance | None = None
    confirmed: bool = False  # a human reviewer signed off on this domain


class RobAssessment(BaseModel):
    """A trial's five-domain RoB 2 appraisal with a deterministic overall roll-up."""

    study_id: str
    label: str
    domains: list[RobDomain] = Field(default_factory=list)
    overall: RobJudgment = RobJudgment.PENDING
    confirmed: bool = False  # all domains signed off


class RobDecision(BaseModel):
    """A human reviewer's sign-off ("Verify") on one RoB 2 domain."""

    study_id: str
    domain_key: str
    decision: str = "confirmed"
    reason: str | None = None
    timestamp: str | None = None


class GradeRating(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class GradeDomain(BaseModel):
    """One GRADE certainty domain and how far it downgrades the rating."""

    name: str  # risk_of_bias | inconsistency | indirectness | imprecision | publication_bias
    serious: str = "not_serious"  # not_serious | serious | very_serious
    downgrade: int = 0  # 0, -1, or -2
    rationale: str = ""
    by_claude: bool = False  # True for the judged domains (indirectness, publication bias)


class EggerResult(BaseModel):
    """Egger's regression test for funnel-plot asymmetry (small-study effects).

    Only meaningful with at least 10 studies (Cochrane Handbook 13.3.5.3); below
    that `applicable` is False and GRADE keeps the qualitative judgment. The
    intercept measures asymmetry, tested at p < 0.10.
    """

    k: int
    intercept: float | None = None
    se_intercept: float | None = None
    t: float | None = None
    p: float | None = None
    applicable: bool = False


class GradeAssessment(BaseModel):
    """Certainty of evidence for one outcome, with a Summary-of-Findings line."""

    outcome: str
    starting_level: GradeRating = GradeRating.HIGH
    certainty: GradeRating = GradeRating.HIGH
    domains: list[GradeDomain] = Field(default_factory=list)
    sof_line: str = ""
    footnotes: list[str] = Field(default_factory=list)
    publication_bias_test: EggerResult | None = None


class LeaveOneOutRow(BaseModel):
    """One leave-one-out sensitivity row: the pool with a single study omitted."""

    omitted_study_id: str
    omitted_label: str
    k: int
    estimate: float
    ci_low: float
    ci_high: float
    i2: float


class StudyResult(BaseModel):
    """Per-study computed effect, for the forest plot rows."""

    study_id: str
    label: str
    yi: float  # effect on the analysis scale (log for ratio measures)
    vi: float  # variance of yi
    effect: float  # natural scale (e.g. RR)
    ci_low: float
    ci_high: float
    weight: float  # percent weight in the pool


class PoolResult(BaseModel):
    """A complete, auditable pooled estimate."""

    measure: EffectMeasure
    model: str = "random"
    method: str = "REML"
    pool_method: PoolMethod = PoolMethod.IV
    engine: str  # "metafor" | "python"
    k: int

    estimate: float  # natural scale
    ci_low: float
    ci_high: float
    ci_method: CIMethod

    estimate_log: float
    se_log: float
    ci_low_log: float
    ci_high_log: float

    tau2: float
    i2: float
    q: float
    q_p: float

    prediction_low: float | None = None
    prediction_high: float | None = None

    studies: list[StudyResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # Data conversions applied to the pooled studies (SE from CI, SMD Hedges' J,
    # SD from SE/CI). Kept distinct from `notes`, which are interpretive caveats.
    assumptions: list[Assumption] = Field(default_factory=list)


class PipelineEvent(BaseModel):
    """A single step in the running pipeline, streamed to the UI."""

    stage: str  # parse | retrieve | extract | validate | pool | done
    message: str
    data: dict | None = None


class ReviewResult(BaseModel):
    """The complete, auditable output of one review run."""

    question: Question
    extractions: list[TrialExtraction] = Field(default_factory=list)
    validations: list[ValidationResult] = Field(default_factory=list)
    pool: PoolResult | None = None
    summary: str = ""
    rob: list[RobAssessment] = Field(default_factory=list)
    grade: GradeAssessment | None = None
    sensitivity: list[LeaveOneOutRow] = Field(default_factory=list)
    diversity: DiversityAssessment | None = None


class TrialCandidate(BaseModel):
    """A trial surfaced by search, before extraction."""

    nct_id: str
    title: str
    source: str = "clinicaltrials.gov"


class ReviewSummary(BaseModel):
    """One row on the Reviews Dashboard — the headline of a saved review."""

    question_id: str
    text: str
    versions: int
    k: int = 0
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    measure: str = "HR"
    status: str = "unchanged"  # unchanged | estimate-updated | conclusion-moved


class SnapshotMeta(BaseModel):
    """One row of a question's version history — the audit-trail timeline.

    Headline pool numbers are denormalized here so the history list renders
    without deserializing each full ReviewResult.
    """

    question_id: str
    version: int
    created_at: str  # ISO-8601, UTC
    k: int = 0
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    measure: str = "HR"


class ReviewDiff(BaseModel):
    """How a re-run compares to the previous snapshot of a question.

    The load-bearing signal for the living layer: did adding a trial move the
    estimate, and — more importantly — did it change the conclusion (flip the
    statistical significance or the direction of effect)?
    """

    question_id: str
    previous_version: int
    current_version: int

    estimate_prev: float | None = None
    estimate_curr: float | None = None
    delta: float | None = None  # estimate_curr - estimate_prev, natural scale

    ci_prev: tuple[float, float] | None = None
    ci_curr: tuple[float, float] | None = None

    k_prev: int
    k_curr: int
    added_trials: list[str] = Field(default_factory=list)

    significance_changed: bool = False
    direction_changed: bool = False
    conclusion_changed: bool = False

    notes: list[str] = Field(default_factory=list)
