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
    SETBACK = "setback"  # a trial halted: terminated / withdrawn / suspended
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

# Sources that are available but off unless a caller names them. ClinicalTrials.gov
# is always on; PubMed (Europe PMC) and openFDA are opt-in per request — a live
# client for either is provisioned only when the source is *explicitly* selected,
# never by the structured-trio default. Keeps every run CT.gov-only unless the
# user asks for more.
OPT_IN_SOURCES = frozenset({Source.PUBMED, Source.OPENFDA})


def explicitly_selected(param: str | None, source: Source | str) -> bool:
    """Was `source` explicitly named in a raw ``sources=`` param?

    Distinct from :meth:`SourceSelection.allows`: the default selection *allows*
    the whole structured trio, but PubMed and openFDA stay off unless a caller
    lists them by name. Front ends use this to decide whether to construct the
    (optional) Europe PMC / openFDA client at all, so they remain opt-in.
    """
    if not param:
        return False
    wanted = source.value if isinstance(source, Source) else str(source).strip().lower()
    tokens = {t.strip().lower() for t in param.split(",")}
    return wanted in tokens


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


class CompanyPipeline(BaseModel):
    """One pharma company's entire pipeline, across all indications and phases.

    The cross-condition sibling of `Landscape`: scoped to a lead sponsor rather
    than a condition, so a card can appear for the same asset in several
    indications. Reuses the same `LandscapeCell` (phase, readout, evidence badge)
    so the board renders identically, and adds the company's FDA `approvals`.
    """

    sponsor: str
    as_of: str | None = None
    assets: list[str] = Field(default_factory=list)
    indications: list[str] = Field(default_factory=list)
    cells: list[LandscapeCell] = Field(default_factory=list)
    approvals: list[RegulatoryApproval] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# v3 — CI as intelligence: change-feed, radar, side-by-side, MoA, NL front door
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    """The kinds of competitive move the change-feed surfaces."""

    NEW_PROGRAM = "new_program"
    ADVANCED = "advanced"
    READOUT = "readout"
    SETBACK = "setback"  # a trial halted (terminated / withdrawn / suspended)
    EVIDENCE_MOVED = "evidence_moved"
    CONFLICT_OPENED = "conflict_opened"


class LandscapeChange(BaseModel):
    """One dated, sourced competitive move between two as-of snapshots.

    The CI analogue of `ReviewDiff`: what changed and — for evidence moves —
    whether the *conclusion* changed, never a fabricated number. Every change
    carries the provenance of the events that produced it.
    """

    asset_name: str
    indication: str
    change_type: ChangeType
    date: str | None = None  # when the move happened, within the window
    from_phase: Phase | None = None
    to_phase: Phase | None = None
    # Evidence moves only — plain-language headline plus the drill-in numbers.
    summary: str = ""  # plain language, e.g. "Advanced to Phase 3"
    estimate_prev: float | None = None
    estimate_curr: float | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class LandscapeDiff(BaseModel):
    """"What moved" in a condition's landscape between two dates."""

    condition: str
    since: str | None = None
    until: str | None = None
    changes: list[LandscapeChange] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MilestoneKind(str, Enum):
    EXPECTED_READOUT = "expected_readout"  # primary completion in the future
    PDUFA = "pdufa"  # regulatory decision expected


class Milestone(BaseModel):
    """A forward-looking, dated event — a readout or decision yet to land."""

    asset_name: str
    indication: str
    nct_id: str = ""
    title: str = ""
    phase: Phase = Phase.UNKNOWN
    kind: MilestoneKind = MilestoneKind.EXPECTED_READOUT
    expected_date: str  # ISO date, in the future relative to as_of
    quarter: str = ""  # e.g. "2026-Q4", derived for bucketing
    sponsor: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class MilestoneRadar(BaseModel):
    """Upcoming readouts/decisions for a condition, bucketed by quarter."""

    scope: str  # the condition (or sponsor) searched
    as_of: str | None = None
    horizon_months: int = 18
    milestones: list[Milestone] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    """One operational attribute lined up across the compared assets.

    Operational only — phase, enrollment, geography, timing. Effect estimates are
    NOT comparison rows; they live in `AssetEvidenceContext`, each in its own
    context, because a cross-trial efficacy comparison is a naive indirect
    comparison the method forbids.
    """

    label: str
    values: list[str] = Field(default_factory=list)  # one per asset, "—" when absent
    # Neutral "this column has more" marker per asset — for counts (enrollment,
    # geography), never for effect estimates. All-false when not applicable.
    more: list[bool] = Field(default_factory=list)


class AssetEvidenceContext(BaseModel):
    """One asset's pooled evidence, presented in its own context — never ranked."""

    asset_name: str
    indication: str = ""
    population: str = ""  # sub-population display, so the reader sees who it's in
    comparator: str | None = None  # labeled so two badges aren't read as one axis
    plain_summary: str = ""  # "benefit proven" / "evidence pending" / "not enough data"
    badge: EvidenceBadge | None = None


class Comparability(BaseModel):
    """The deterministic gate: are two assets' estimates directly comparable?

    Almost always false across separate meta-analyses. When false, the UI shows an
    "Indirect — not directly comparable" banner listing `reasons`, and never a
    shared axis or a winner.
    """

    directly_comparable: bool = False
    reasons: list[str] = Field(default_factory=list)


class AssetComparison(BaseModel):
    """A side-by-side profile: operational facts compared, efficacy abstained."""

    assets: list[str] = Field(default_factory=list)
    indication: str | None = None
    rows: list[ComparisonRow] = Field(default_factory=list)
    evidence: list[AssetEvidenceContext] = Field(default_factory=list)
    comparability: Comparability = Field(default_factory=Comparability)
    notes: list[str] = Field(default_factory=list)


class MoaCluster(BaseModel):
    """The competitive field for one mechanism, with class-level evidence."""

    drug_class: str
    label: str = ""
    assets: list[str] = Field(default_factory=list)
    program_count: int = 0
    stage_distribution: dict[str, int] = Field(default_factory=dict)
    plain_summary: str = ""  # plain-language class evidence line
    evidence: EvidenceBadge | None = None


class MoaLandscape(BaseModel):
    """A condition's assets grouped by mechanism of action."""

    condition: str
    clusters: list[MoaCluster] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MarketQuery(BaseModel):
    """Claude's structured read of a free-text market-intelligence question.

    The chat's brain: map plain language to one deterministic tool plus its
    params. Code then executes the tool; Claude never computes the figures.
    """

    tool: str = "landscape"  # landscape|changes|compare|radar|moa|dossier|company|indication
    condition: str | None = None
    assets: list[str] = Field(default_factory=list)
    indication: str | None = None
    sponsor: str | None = None
    since: str | None = None
    until: str | None = None
    as_of: str | None = None
    horizon_months: int | None = None
    confidence: str = "low"  # high | moderate | low
    reason: str = ""  # why this route was chosen


class MarketAnswer(BaseModel):
    """The chat's response: the routed tool's typed payload + a grounded narrative."""

    text: str  # the original question
    intent: MarketQuery
    tool: str = "landscape"
    result: dict = Field(default_factory=dict)  # serialized view model for the front door
    narrative: str = ""  # plain-language, numbers quoted from `result`
    suggestions: list[str] = Field(default_factory=list)  # follow-up chips
    notes: list[str] = Field(default_factory=list)
