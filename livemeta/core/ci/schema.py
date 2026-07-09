"""Schema for the competitive-intelligence layer.

These models *reference* the meta-analysis by `question_id` and reuse its
`Provenance` atom, so a competitive claim ("Phase 3") and a pooled effect
("HR 0.86") carry the same kind of source snippet. Everything here is additive:
the meta-analysis schema is untouched, and the GLP-1 HR demo is unaffected.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..schema import Provenance, TrialExtraction


class Phase(str, Enum):
    """Development stage, ordered by `PHASE_RANK` for "most advanced" roll-ups."""

    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"
    FILED = "filed"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


# Ordering for reconciliation: a later, more-advanced stage wins. WITHDRAWN and
# UNKNOWN sort below everything so a real stage is always preferred over them.
PHASE_RANK: dict[Phase, int] = {
    Phase.WITHDRAWN: -2,
    Phase.UNKNOWN: -1,
    Phase.PRECLINICAL: 0,
    Phase.PHASE_1: 1,
    Phase.PHASE_1_2: 2,
    Phase.PHASE_2: 3,
    Phase.PHASE_2_3: 4,
    Phase.PHASE_3: 5,
    Phase.PHASE_4: 6,
    Phase.FILED: 7,
    Phase.APPROVED: 8,
}


def phase_rank(phase: Phase) -> int:
    return PHASE_RANK.get(phase, -1)


class SourceType(str, Enum):
    CTGOV = "ctgov"
    ANNOUNCEMENT = "announcement"
    FILING = "filing"


class EventType(str, Enum):
    TRIAL_START = "trial_start"
    TRIAL_STATUS = "trial_status"
    READOUT = "readout"
    FILING = "filing"
    APPROVAL = "approval"
    ANNOUNCEMENT = "announcement"


class Asset(BaseModel):
    """A compound's identity, with the source it was read from."""

    name: str
    aliases: list[str] = Field(default_factory=list)
    sponsor: str | None = None
    sponsor_class: str | None = None  # INDUSTRY | NIH | OTHER (CT.gov leadSponsor.class)
    drug_class: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class DevelopmentEvent(BaseModel):
    """The dated, sourced atom of the pipeline time series.

    Every state a drug has been in is one of these, so "the pipeline as of date T"
    is a pure filter over events. Each carries `provenance` — no stage claim
    without a source snippet.
    """

    asset_name: str
    indication: str
    line_of_therapy: str | None = None
    phase: Phase = Phase.UNKNOWN
    status: str | None = None
    event_type: EventType = EventType.TRIAL_STATUS
    date: str | None = None  # ISO date (YYYY-MM-DD); None when the source omits it
    source_type: SourceType = SourceType.CTGOV
    sponsor: str | None = None
    sponsor_class: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class ExtractedDevelopmentEvent(BaseModel):
    """Claude's structured read of a free-text announcement/filing.

    The sibling of `extract_text.ExtractedEffect`: Claude reports what the
    document says (with the exact snippet and a self-reported confidence); code
    maps it to a `DevelopmentEvent` and drops/flags anything low-confidence. The
    model never asserts a stage the text does not state.
    """

    found: bool = False
    confidence: str = "low"  # high | moderate | low
    source_snippet: str = ""

    asset_name: str = ""
    sponsor: str | None = None
    indication: str = ""
    line_of_therapy: str | None = None
    phase: str = "unknown"  # free string; mapped to Phase in code
    event_type: str = "announcement"
    date: str | None = None


class EvidenceBadge(BaseModel):
    """The living pooled-evidence summary denormalized onto a landscape cell.

    `state` distinguishes the three honest outcomes of the evidence layer so a
    cell never shows a fabricated number: a committed pool, a pool withheld
    pending a homogeneity confirmation, or an abstention (too few / no data).
    """

    question_id: str
    measure: str = "HR"
    state: str = "abstained"  # pooled | gate_open | abstained
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    grade_certainty: str | None = None
    conclusion: str | None = None  # human-readable, e.g. "significant reduction"
    version: int | None = None
    k: int = 0


class LandscapeCell(BaseModel):
    """One asset × indication(× line) rollup, as of a date."""

    asset_name: str
    indication: str
    line_of_therapy: str | None = None
    current_phase: Phase = Phase.UNKNOWN
    status: str | None = None
    sponsor: str | None = None
    sponsor_class: str | None = None
    latest_event: DevelopmentEvent | None = None
    conflict: bool = False
    conflict_note: str | None = None
    question_id: str | None = None
    evidence: EvidenceBadge | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class Landscape(BaseModel):
    """The assembled competitive matrix for a condition, at one point in time.

    The matrix axes are `assets` (rows) × `indications` (columns) — the two the
    structured CT.gov record actually populates. Line of therapy, when a source
    supplies it, lives on the cell; it is not the column axis because CT.gov
    rarely states it.
    """

    condition: str
    as_of: str | None = None
    assets: list[str] = Field(default_factory=list)
    indications: list[str] = Field(default_factory=list)
    cells: list[LandscapeCell] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# v2 — Deep CI: source selection, sub-populations, trial detail, dossiers, maps
# ---------------------------------------------------------------------------


class Source(str, Enum):
    """A selectable data source. The structured three are the authoritative core;
    the free-text two are Claude-read and off by default."""

    CTGOV = "ctgov"
    PUBMED = "pubmed"  # Europe PMC / PubMed
    OPENFDA = "openfda"
    ANNOUNCEMENT = "announcement"
    FILING = "filing"


STRUCTURED_SOURCES = frozenset({Source.CTGOV, Source.PUBMED, Source.OPENFDA})
FREE_TEXT_SOURCES = frozenset({Source.ANNOUNCEMENT, Source.FILING})


class SourceSelection(BaseModel):
    """Which sources the platform is allowed to use. Default: structured only.

    One selection is threaded through every builder so the user can exclude
    anything that isn't from ClinicalTrials.gov / PubMed / openFDA. Free-text
    (announcement/filing) is opt-in.
    """

    enabled: list[Source] = Field(default_factory=lambda: list(STRUCTURED_SOURCES))

    def allows(self, source: Source | SourceType | str) -> bool:
        value = source.value if isinstance(source, (Source, SourceType)) else str(source)
        try:
            return Source(value) in set(self.enabled)
        except ValueError:
            return False

    @property
    def free_text_enabled(self) -> bool:
        return any(s in FREE_TEXT_SOURCES for s in self.enabled)

    @classmethod
    def default(cls) -> "SourceSelection":
        return cls(enabled=list(STRUCTURED_SOURCES))

    @classmethod
    def from_param(cls, param: str | None) -> "SourceSelection":
        """Parse a `sources=ctgov,pubmed,openfda` query param; None -> default."""
        if not param:
            return cls.default()
        chosen: list[Source] = []
        for token in param.split(","):
            token = token.strip().lower()
            if not token:
                continue
            try:
                chosen.append(Source(token))
            except ValueError:
                continue  # ignore unknown tokens rather than erroring
        return cls(enabled=chosen or list(STRUCTURED_SOURCES))


class SubPopulation(BaseModel):
    """A trial's precise target population, refining a top-level indication.

    Claude reads the eligibility text into this structure; a deterministic
    `signature()` clusters trials with the same target into one indication node
    (e.g. "obesity + established CVD, adults >=45"). When unread, it degrades to
    the base indication alone — never a fabricated sub-group.
    """

    base_indication: str
    age_min: int | None = None
    age_max: int | None = None
    sex: str | None = None  # ALL | MALE | FEMALE
    comorbidities: list[str] = Field(default_factory=list)  # e.g. established_cvd, ckd, t2d
    line_of_therapy: str | None = None
    prior_treatment: str | None = None
    label: str = ""
    provenance: list[Provenance] = Field(default_factory=list)

    def signature(self) -> str:
        """Canonical clustering key — trials with the same key share a node."""
        comorbid = "+".join(sorted(c.strip().lower() for c in self.comorbidities if c.strip()))
        age = f"{self.age_min if self.age_min is not None else ''}-{self.age_max if self.age_max is not None else ''}"
        parts = [
            self.base_indication.strip().lower(),
            (self.sex or "all").lower(),
            age if age != "-" else "",
            comorbid,
            (self.line_of_therapy or "").lower(),
        ]
        return "|".join(p for p in parts if p)

    def display(self) -> str:
        """A human label, derived if Claude didn't supply one."""
        if self.label:
            return self.label
        bits = [self.base_indication]
        if self.comorbidities:
            bits.append("+ " + ", ".join(self.comorbidities))
        if self.age_min:
            bits.append(f"adults >={self.age_min}")
        if self.sex and self.sex.upper() not in ("ALL", ""):
            bits.append(self.sex.lower())
        return " ".join(bits)


class TrialDetail(BaseModel):
    """One trial as it appears in an asset dossier / indication map."""

    nct_id: str
    title: str = ""
    asset_name: str = ""
    phase: Phase = Phase.UNKNOWN
    status: str | None = None
    enrollment: int | None = None
    start_date: str | None = None
    primary_completion_date: str | None = None
    results_posted_date: str | None = None
    has_results: bool = False
    sponsor: str | None = None
    sponsor_class: str | None = None
    countries: list[str] = Field(default_factory=list)
    indication: str = ""
    sub_population: SubPopulation | None = None
    effect: TrialExtraction | None = None  # headline effect when the trial has read out
    provenance: list[Provenance] = Field(default_factory=list)


class RegulatoryApproval(BaseModel):
    """A regulatory approval from openFDA (drug / sponsor / date / brand)."""

    drug: str
    sponsor: str | None = None
    application_number: str
    brand_names: list[str] = Field(default_factory=list)
    approval_date: str | None = None
    marketing_status: str | None = None
    indication_approx: str | None = None  # openFDA omits indication text; approximate only
    provenance: list[Provenance] = Field(default_factory=list)


class CountryCount(BaseModel):
    country: str
    trials: int


class SubIndicationGroup(BaseModel):
    """A dossier's trials grouped by the sub-population they target."""

    signature: str
    label: str
    trial_ids: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    evidence: EvidenceBadge | None = None


class AssetDossier(BaseModel):
    """Everything known about one asset, aggregated across its trials."""

    asset: Asset
    sources: list[Source] = Field(default_factory=list)
    trials: list[TrialDetail] = Field(default_factory=list)
    countries: list[CountryCount] = Field(default_factory=list)
    events: list[DevelopmentEvent] = Field(default_factory=list)
    readouts: list[TrialDetail] = Field(default_factory=list)
    approvals: list[RegulatoryApproval] = Field(default_factory=list)
    sub_indications: list[SubIndicationGroup] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IndicationNode(BaseModel):
    """One sub-population within an indication, with its competitive field."""

    signature: str
    label: str
    sub_population: SubPopulation | None = None
    assets: list[str] = Field(default_factory=list)
    trial_count: int = 0
    stage_distribution: dict[str, int] = Field(default_factory=dict)
    countries: list[CountryCount] = Field(default_factory=list)
    approvals: list[RegulatoryApproval] = Field(default_factory=list)
    evidence: EvidenceBadge | None = None


class IndicationMap(BaseModel):
    """An indication broken into its sub-populations, bottom-up from the trials."""

    indication: str
    sources: list[Source] = Field(default_factory=list)
    nodes: list[IndicationNode] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
