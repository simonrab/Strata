"""Asset dossier + indication map aggregation, and the source-selection filter."""

from livemeta.core.ci.dossier import build_asset_dossier
from livemeta.core.ci.indication import build_indication_map
from livemeta.core.ci.schema import (
    DevelopmentEvent,
    EventType,
    EvidenceBadge,
    Phase,
    RegulatoryApproval,
    Source,
    SourceSelection,
    SourceType,
    SubPopulation,
    TrialDetail,
)
from livemeta.core.schema import Provenance


def _trial(nct, asset="Semaglutide", phase=Phase.PHASE_3, indication="Obesity",
           countries=("United States",), has_results=False, subpop=None):
    return TrialDetail(
        nct_id=nct, asset_name=asset, phase=phase, indication=indication,
        countries=list(countries), has_results=has_results, sponsor="Novo Nordisk",
        sub_population=subpop,
        provenance=[Provenance(trial_id=nct, snippet="s")],
    )


def _event(asset="Semaglutide", source=SourceType.CTGOV):
    return DevelopmentEvent(
        asset_name=asset, indication="Obesity", phase=Phase.PHASE_3,
        event_type=EventType.TRIAL_START, source_type=source,
        provenance=[Provenance(trial_id="NCT1", snippet="s")],
    )


# --- Asset dossier ----------------------------------------------------------


def test_dossier_aggregates_trials_countries_and_readouts():
    trials = [
        _trial("NCT1", countries=("United States", "Germany"), has_results=True),
        _trial("NCT2", countries=("United States",)),
    ]
    d = build_asset_dossier("Semaglutide", trials, [_event()])
    assert d.asset.name == "Semaglutide"
    assert len(d.trials) == 2
    assert len(d.readouts) == 1 and d.readouts[0].nct_id == "NCT1"
    # US appears in both trials -> ranked first
    assert d.countries[0].country == "United States" and d.countries[0].trials == 2
    assert {c.country for c in d.countries} == {"United States", "Germany"}


def test_dossier_groups_by_subpopulation_when_present():
    cv = SubPopulation(base_indication="Obesity", comorbidities=["established_cvd"], age_min=45)
    plain = SubPopulation(base_indication="Obesity")
    trials = [
        _trial("NCT1", subpop=cv), _trial("NCT2", subpop=cv), _trial("NCT3", subpop=plain),
    ]
    d = build_asset_dossier("Semaglutide", trials, [])
    sigs = {g.signature: g.trial_ids for g in d.sub_indications}
    assert len(sigs) == 2
    cv_group = next(g for g in d.sub_indications if "established_cvd" in g.signature)
    assert set(cv_group.trial_ids) == {"NCT1", "NCT2"}


def test_dossier_evidence_resolver_attaches_badge():
    def resolver(asset, indication):
        return EvidenceBadge(question_id="q", measure="HR", state="pooled",
                             estimate=0.8, conclusion="significant reduction")
    d = build_asset_dossier("Semaglutide", [_trial("NCT1")], [], evidence_for=resolver)
    assert d.sub_indications[0].evidence.state == "pooled"


# --- Source selection -------------------------------------------------------


def test_free_text_events_dropped_by_default():
    events = [_event(source=SourceType.CTGOV), _event(source=SourceType.ANNOUNCEMENT)]
    d = build_asset_dossier("Semaglutide", [_trial("NCT1")], events)  # default = structured only
    assert [e.source_type for e in d.events] == [SourceType.CTGOV]


def test_free_text_events_kept_when_enabled():
    events = [_event(source=SourceType.CTGOV), _event(source=SourceType.ANNOUNCEMENT)]
    sel = SourceSelection.from_param("ctgov,announcement")
    d = build_asset_dossier("Semaglutide", [_trial("NCT1")], events, selection=sel)
    assert len(d.events) == 2


def test_approvals_only_when_openfda_enabled():
    approvals = [RegulatoryApproval(drug="Semaglutide", application_number="NDA1")]
    # default includes OPENFDA
    d1 = build_asset_dossier("Semaglutide", [_trial("NCT1")], [], approvals=approvals)
    assert len(d1.approvals) == 1
    # turn openFDA off
    sel = SourceSelection.from_param("ctgov,pubmed")
    d2 = build_asset_dossier("Semaglutide", [_trial("NCT1")], [], approvals=approvals, selection=sel)
    assert d2.approvals == []


# --- Indication map ---------------------------------------------------------


def test_indication_map_clusters_by_subpopulation():
    cv = SubPopulation(base_indication="Obesity", comorbidities=["established_cvd"])
    old = SubPopulation(base_indication="Obesity", age_min=65)
    trials = [
        _trial("NCT1", asset="Semaglutide", subpop=cv),
        _trial("NCT2", asset="Tirzepatide", subpop=cv),
        _trial("NCT3", asset="Retatrutide", phase=Phase.PHASE_2, subpop=old),
    ]
    m = build_indication_map("Obesity", trials)
    assert len(m.nodes) == 2
    cv_node = next(n for n in m.nodes if "established_cvd" in n.signature)
    assert set(cv_node.assets) == {"Semaglutide", "Tirzepatide"}
    assert cv_node.trial_count == 2
    assert cv_node.stage_distribution == {"phase_3": 2}


def test_indication_map_falls_back_to_base_indication_without_subpop():
    trials = [_trial("NCT1"), _trial("NCT2")]
    m = build_indication_map("Obesity", trials)
    assert len(m.nodes) == 1
    assert m.nodes[0].trial_count == 2
