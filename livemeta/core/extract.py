"""Extract effect data from ClinicalTrials.gov v2 structured results.

Safety-first: take the hazard ratio straight from the structured `analyses`
field, attach provenance (the outcome title and the exact reported figure), and
flag rather than guess when it is absent. No silent back-calculation.
"""

from __future__ import annotations

import os

from .schema import (
    RATIO_MEASURES as _RATIO_MEASURES,
    Assumption,
    BinaryArm,
    BinaryEffect,
    ContinuousArm,
    ContinuousEffect,
    EffectMeasure,
    Provenance,
    TrialExtraction,
)
from .stats import escalc

# Measures that come from a 2x2 table vs a mean/SD table.
_BINARY_MEASURES = {EffectMeasure.RR, EffectMeasure.OR}
_CONTINUOUS_MEASURES = {EffectMeasure.MD, EffectMeasure.SMD}


def _identity(study_json: dict) -> tuple[str, str]:
    ident = study_json.get("protocolSection", {}).get("identificationModule", {})
    nct = ident.get("nctId", "UNKNOWN")
    label = ident.get("briefTitle") or ident.get("officialTitle") or nct
    return nct, label


def _find_hr_analysis(outcome_measures: list[dict]) -> tuple[dict, dict] | None:
    """Return (outcome_measure, analysis) for the first hazard-ratio analysis,
    preferring PRIMARY outcomes."""
    ordered = sorted(
        outcome_measures, key=lambda om: 0 if om.get("type") == "PRIMARY" else 1
    )
    for om in ordered:
        for analysis in om.get("analyses", []):
            if "Hazard Ratio" in (analysis.get("paramType") or ""):
                return om, analysis
    return None


def extract_hr(study_json: dict) -> TrialExtraction:
    """Extract the primary hazard ratio (e.g. MACE) with provenance."""
    nct, label = _identity(study_json)
    source_url = f"https://clinicaltrials.gov/study/{nct}"
    oms = (
        study_json.get("resultsSection", {})
        .get("outcomeMeasuresModule", {})
        .get("outcomeMeasures", [])
    )

    found = _find_hr_analysis(oms)
    if found is None:
        return TrialExtraction(
            study_id=nct,
            label=label,
            flagged=True,
            flag_reason="No hazard-ratio analysis found in structured results.",
            provenance=[Provenance(trial_id=nct, snippet="", source_url=source_url)],
        )

    om, analysis = found
    try:
        hr = float(analysis["paramValue"])
        ci_low = float(analysis["ciLowerLimit"])
        ci_high = float(analysis["ciUpperLimit"])
    except (KeyError, TypeError, ValueError):
        return TrialExtraction(
            study_id=nct,
            label=label,
            flagged=True,
            flag_reason="Hazard ratio present but its value or CI is incomplete.",
            provenance=[
                Provenance(
                    trial_id=nct,
                    snippet=om.get("title", ""),
                    source_url=source_url,
                    field="outcomeMeasures.analyses",
                )
            ],
        )

    # Capture the clinical endpoint and the compared arms from the same analysis,
    # so the homogeneity gate can check outcome consistency and a reviewer can
    # verify effect direction from the arms it names.
    endpoint = om.get("title")
    comparison_arms = _comparison_arms(om, analysis)

    arms_note = f" [arms: {' vs '.join(comparison_arms)}]" if comparison_arms else ""
    snippet = (
        f"{om.get('title', 'Primary outcome')}: HR {hr} ({ci_low}-{ci_high}){arms_note}"
    )
    provenance = [
        Provenance(
            trial_id=nct,
            snippet=snippet,
            source_url=source_url,
            field="outcomeMeasures.analyses.paramValue",
        )
    ]
    point = escalc.ratio_ci_point(nct, label, hr, ci_low, ci_high, provenance)

    return TrialExtraction(
        study_id=nct,
        label=label,
        measure=EffectMeasure.HR,
        endpoint=endpoint,
        comparison_arms=comparison_arms,
        hr=hr,
        ci_low=ci_low,
        ci_high=ci_high,
        point=point,
        provenance=provenance,
        assumptions=point.assumptions,
    )


def _comparison_arms(om: dict, analysis: dict) -> list[str]:
    """The arm labels this ratio compares, in the order CT.gov lists them.

    Surfaced for human verification of effect direction. Deliberately NOT read as
    numerator/denominator: CT.gov's `groupIds` order is not a reliable
    treatment-vs-comparator signal — several GLP-1 CVOTs list placebo first while
    still reporting a conventional drug-vs-placebo hazard ratio — so orientation is
    a reviewer's call, not a value we infer from group order.
    """
    titles = {g.get("id"): g.get("title") for g in om.get("groups", [])}
    gids = analysis.get("groupIds") or []
    return [titles[g] for g in gids if titles.get(g)]


# --- Binary (2x2) and continuous (mean/SD/n) extraction ---------------------
#
# CT.gov v2 reports arm-level results in `outcomeMeasures[].classes[].categories[]
# .measurements[]`, keyed by the group ids in `denoms`. A binary outcome is a
# COUNT_OF_PARTICIPANTS measure (events per arm) with participant denominators; a
# continuous outcome is a MEAN measure whose measurements carry a `spread` (the
# SD). We read the first two-arm outcome, preferring PRIMARY, and flag rather
# than guess when the structure is absent or ambiguous.


def _first_outcome(oms: list[dict], param_types: set[str]) -> dict | None:
    ordered = sorted(oms, key=lambda om: 0 if om.get("type") == "PRIMARY" else 1)
    for om in ordered:
        if (om.get("paramType") or "").upper() in param_types:
            return om
    return None


def _arm_group_ids(om: dict) -> list[str]:
    """The (up to two) group ids for the treatment and control arms, in order."""
    denoms = om.get("denoms") or []
    if denoms and denoms[0].get("counts"):
        return [c.get("groupId") for c in denoms[0]["counts"]]
    return [g.get("id") for g in om.get("groups", [])]


def _denom_totals(om: dict) -> dict[str, int]:
    denoms = om.get("denoms") or []
    if not denoms:
        return {}
    return {
        c.get("groupId"): int(float(c["value"]))
        for c in denoms[0].get("counts", [])
        if c.get("value") not in (None, "")
    }


def _first_measurements(om: dict) -> list[dict]:
    for cls in om.get("classes", []):
        for cat in cls.get("categories", []):
            meas = cat.get("measurements")
            if meas:
                return meas
    return []


def extract_binary(
    study_json: dict, measure: EffectMeasure = EffectMeasure.RR
) -> TrialExtraction:
    """Extract a 2x2 table (events/totals per arm) from CT.gov structured results."""
    nct, label = _identity(study_json)
    source_url = f"https://clinicaltrials.gov/study/{nct}"
    oms = (
        study_json.get("resultsSection", {})
        .get("outcomeMeasuresModule", {})
        .get("outcomeMeasures", [])
    )
    om = _first_outcome(oms, {"COUNT_OF_PARTICIPANTS", "NUMBER OF PARTICIPANTS"})
    group_ids = _arm_group_ids(om) if om else []
    totals = _denom_totals(om) if om else {}
    meas = {m.get("groupId"): m for m in _first_measurements(om)} if om else {}

    if om is None or len(group_ids) < 2 or len(totals) < 2:
        return _flagged(nct, label, source_url, "No structured 2x2 event counts found.")

    t_gid, c_gid = group_ids[0], group_ids[1]
    try:
        a, n1 = int(float(meas[t_gid]["value"])), totals[t_gid]
        c, n2 = int(float(meas[c_gid]["value"])), totals[c_gid]
    except (KeyError, TypeError, ValueError):
        return _flagged(nct, label, source_url, "Event counts present but incomplete.")

    snippet = f"{om.get('title', 'Primary outcome')}: {a}/{n1} vs {c}/{n2}"
    provenance = [
        Provenance(
            trial_id=nct,
            snippet=snippet,
            source_url=source_url,
            field="outcomeMeasures.classes.categories.measurements",
        )
    ]
    binary = BinaryEffect(
        study_id=nct,
        label=label,
        treatment=BinaryArm(events=a, total=n1),
        control=BinaryArm(events=c, total=n2),
        provenance=provenance,
    )
    # A zero cell routes to rare-event (Peto) pooling downstream from `binary`,
    # so build the inverse-variance point defensively and leave it None if the
    # ratio is undefined here.
    try:
        point = escalc.binary_point(binary, measure)
    except ValueError:
        point = None  # zero cell — the engine's Peto route handles it from `binary`

    return TrialExtraction(
        study_id=nct,
        label=label,
        measure=measure,
        binary=binary,
        point=point,
        provenance=provenance,
        assumptions=point.assumptions if point else [],
    )


def extract_continuous(
    study_json: dict, measure: EffectMeasure = EffectMeasure.MD
) -> TrialExtraction:
    """Extract mean/SD/n per arm from CT.gov structured results."""
    nct, label = _identity(study_json)
    source_url = f"https://clinicaltrials.gov/study/{nct}"
    oms = (
        study_json.get("resultsSection", {})
        .get("outcomeMeasuresModule", {})
        .get("outcomeMeasures", [])
    )
    om = _first_outcome(oms, {"MEAN", "LEAST SQUARES MEAN"})
    group_ids = _arm_group_ids(om) if om else []
    totals = _denom_totals(om) if om else {}
    meas = {m.get("groupId"): m for m in _first_measurements(om)} if om else {}

    if om is None or len(group_ids) < 2 or len(totals) < 2:
        return _flagged(nct, label, source_url, "No structured mean/SD per arm found.")
    if (om.get("dispersionType") or "").upper() not in ("STANDARD_DEVIATION", "STANDARD DEVIATION"):
        return _flagged(
            nct, label, source_url, "Continuous outcome does not report a standard deviation."
        )

    t_gid, c_gid = group_ids[0], group_ids[1]
    try:
        m1, sd1, n1 = float(meas[t_gid]["value"]), float(meas[t_gid]["spread"]), totals[t_gid]
        m2, sd2, n2 = float(meas[c_gid]["value"]), float(meas[c_gid]["spread"]), totals[c_gid]
    except (KeyError, TypeError, ValueError):
        return _flagged(nct, label, source_url, "Mean/SD present but incomplete.")

    snippet = (
        f"{om.get('title', 'Primary outcome')}: {m1}±{sd1} (n={n1}) vs {m2}±{sd2} (n={n2})"
    )
    provenance = [
        Provenance(
            trial_id=nct,
            snippet=snippet,
            source_url=source_url,
            field="outcomeMeasures.classes.categories.measurements",
        )
    ]
    continuous = ContinuousEffect(
        study_id=nct,
        label=label,
        treatment=ContinuousArm(mean=m1, sd=sd1, n=n1),
        control=ContinuousArm(mean=m2, sd=sd2, n=n2),
        provenance=provenance,
    )
    point = escalc.continuous_point(continuous, measure)

    return TrialExtraction(
        study_id=nct,
        label=label,
        measure=measure,
        continuous=continuous,
        point=point,
        provenance=provenance,
        assumptions=point.assumptions,
    )


def _flagged(nct: str, label: str, source_url: str, reason: str) -> TrialExtraction:
    return TrialExtraction(
        study_id=nct,
        label=label,
        flagged=True,
        flag_reason=reason,
        provenance=[Provenance(trial_id=nct, snippet="", source_url=source_url)],
    )


def extract(study_json: dict, measure: EffectMeasure) -> TrialExtraction:
    """Route to the right structured extractor for the question's measure.

    HR (and RR/OR reported as a ratio+CI) → `extract_hr`; RR/OR from event
    counts → `extract_binary`; MD/SMD → `extract_continuous`. For `measure=HR`
    this is exactly the pre-existing `extract_hr` path.
    """
    if measure in _CONTINUOUS_MEASURES:
        return extract_continuous(study_json, measure)
    if measure in _BINARY_MEASURES:
        ext = extract_binary(study_json, measure)
        # If no 2x2 table is present, fall back to a reported ratio+CI (some
        # trials report RR/OR directly in the analyses block, like HR).
        if ext.flagged:
            ratio = extract_hr(study_json)
            if not ratio.flagged:
                ratio.measure = measure
                return ratio
        return ext
    return extract_hr(study_json)


def extract_any(
    doc: dict, measure: EffectMeasure, llm_client=None
) -> TrialExtraction:
    """Extract from a fetched record, choosing structured vs text by its shape.

    A Europe PMC document (`source == "europepmc"`) is unstructured text and goes
    to Claude via `extract_from_text`; a ClinicalTrials.gov record has structured
    results and goes to `extract`. This is the single entry point the pipeline
    uses so a mixed-source review reads each trial the right way.
    """
    if doc.get("source") == "europepmc":
        return extract_from_text(doc, measure, llm_client=llm_client)
    return extract(doc, measure)


# --- Text extraction (Europe PMC): Claude reads, code computes --------------


def extract_from_text(
    source_doc: dict, measure: EffectMeasure, llm_client=None
) -> TrialExtraction:
    """Structure a published trial's effect from unstructured text, via Claude.

    Claude reads the abstract/full text/tables and returns one effect variant
    with a source snippet; code turns it into an `EffectPoint`, logging any
    SE↔SD/CI↔SD conversion as an assumption. Keyless, not-found, and
    low-confidence reads are flagged — the tool abstains rather than invents
    precision (CLAUDE.md).
    """
    from . import extract_text as et_mod

    ref_id = source_doc.get("id", "UNKNOWN")
    label = source_doc.get("title") or ref_id
    source_url = f"https://europepmc.org/article/{ref_id.replace(':', '/')}"

    client = llm_client
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            client = anthropic.Anthropic()
        except Exception:
            client = None

    if client is None:
        return _flagged(
            ref_id, label, source_url, "Text extraction requires the model (no key configured)."
        )

    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", "claude-haiku-4-5-20251001")
        parsed: et_mod.ExtractedEffect = client.messages.parse(
            model=model,
            max_tokens=1024,
            system=et_mod.system_hint(),
            messages=[{"role": "user", "content": et_mod.build_prompt(source_doc)}],
            output_format=et_mod.ExtractedEffect,
        ).parsed_output
    except Exception:
        return _flagged(ref_id, label, source_url, "Model read of the published text failed.")

    if not parsed.found or parsed.confidence == "low":
        reason = (
            "Effect not clearly reported in the published text."
            if not parsed.found
            else "Low-confidence read of the published text — routed to manual review."
        )
        return _flagged(ref_id, label, source_url, reason)

    provenance = [
        Provenance(
            trial_id=ref_id,
            snippet=parsed.source_snippet,
            source_url=source_url,
            field=f"europepmc.{parsed.variant}",
        )
    ]
    try:
        return _text_variant_to_extraction(parsed, measure, ref_id, label, provenance)
    except (ValueError, TypeError):
        return _flagged(
            ref_id, label, source_url, "Reported statistics were incomplete or inconsistent."
        )


def _text_variant_to_extraction(parsed, measure, ref_id, label, provenance):
    """Turn a validated ExtractedEffect into a poolable TrialExtraction."""
    if parsed.variant == "binary":
        binary = BinaryEffect(
            study_id=ref_id,
            label=label,
            treatment=BinaryArm(events=parsed.events_treatment, total=parsed.total_treatment),
            control=BinaryArm(events=parsed.events_control, total=parsed.total_control),
            provenance=provenance,
        )
        eff_measure = measure if measure in _BINARY_MEASURES else EffectMeasure.RR
        try:
            point = escalc.binary_point(binary, eff_measure)
        except ValueError:
            point = None  # zero cell — Peto route handles it from `binary`
        return TrialExtraction(
            study_id=ref_id,
            label=label,
            measure=eff_measure,
            binary=binary,
            point=point,
            provenance=provenance,
            assumptions=point.assumptions if point else [],
        )

    if parsed.variant == "continuous":
        assumptions: list[Assumption] = []
        sd1 = _resolve_sd(parsed.sd_treatment, parsed.se_treatment,
                          parsed.ci_low_treatment, parsed.ci_high_treatment,
                          parsed.n_treatment, ref_id, assumptions)
        sd2 = _resolve_sd(parsed.sd_control, parsed.se_control,
                          parsed.ci_low_control, parsed.ci_high_control,
                          parsed.n_control, ref_id, assumptions)
        continuous = ContinuousEffect(
            study_id=ref_id,
            label=label,
            treatment=ContinuousArm(mean=parsed.mean_treatment, sd=sd1, n=parsed.n_treatment),
            control=ContinuousArm(mean=parsed.mean_control, sd=sd2, n=parsed.n_control),
            provenance=provenance,
        )
        eff_measure = measure if measure in _CONTINUOUS_MEASURES else EffectMeasure.MD
        point = escalc.continuous_point(continuous, eff_measure)
        return TrialExtraction(
            study_id=ref_id,
            label=label,
            measure=eff_measure,
            continuous=continuous,
            point=point,
            provenance=provenance,
            assumptions=assumptions + point.assumptions,
        )

    if parsed.variant == "ratio_ci":
        point = escalc.ratio_ci_point(
            ref_id, label, parsed.ratio, parsed.ci_low, parsed.ci_high, provenance
        )
        eff_measure = measure if measure in _RATIO_MEASURES else EffectMeasure.HR
        return TrialExtraction(
            study_id=ref_id,
            label=label,
            measure=eff_measure,
            hr=parsed.ratio,
            ci_low=parsed.ci_low,
            ci_high=parsed.ci_high,
            point=point,
            provenance=provenance,
            assumptions=point.assumptions,
        )

    raise ValueError(f"unknown variant {parsed.variant!r}")


def _resolve_sd(sd, se, ci_low, ci_high, n, ref_id, assumptions: list) -> float:
    """Return an SD directly, or recover it from an SE/CI and log the conversion."""
    if sd is not None:
        return sd
    if se is not None and n is not None:
        value, assumption = escalc.sd_from_se(se, n, ref_id)
        assumptions.append(assumption)
        return value
    if ci_low is not None and ci_high is not None and n is not None:
        value, assumption = escalc.sd_from_ci(ci_low, ci_high, n, ref_id)
        assumptions.append(assumption)
        return value
    raise ValueError("no dispersion (SD/SE/CI) available to build a continuous effect")
