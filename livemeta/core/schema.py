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


class CIMethod(str, Enum):
    WALD = "wald"
    HKSJ = "hksj"  # Hartung-Knapp-Sidik-Jonkman (t-distribution)


class Provenance(BaseModel):
    """Where a value came from — trial ID plus the exact source snippet."""

    trial_id: str
    snippet: str
    source_url: str | None = None
    field: str | None = None


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


class TrialExtraction(BaseModel):
    """A trial's extracted effect with provenance, or a flag for review."""

    study_id: str  # e.g. NCT id
    label: str
    measure: EffectMeasure = EffectMeasure.HR
    hr: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    point: EffectPoint | None = None
    flagged: bool = False
    flag_reason: str | None = None
    confirmed: bool = False  # a human reviewer signed off on this extraction
    provenance: list[Provenance] = Field(default_factory=list)


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
