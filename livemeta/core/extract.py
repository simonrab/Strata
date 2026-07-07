"""Extract effect data from ClinicalTrials.gov v2 structured results.

Safety-first: take the hazard ratio straight from the structured `analyses`
field, attach provenance (the outcome title and the exact reported figure), and
flag rather than guess when it is absent. No silent back-calculation.
"""

from __future__ import annotations

from .schema import EffectMeasure, Provenance, TrialExtraction
from .stats import escalc


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

    snippet = f"{om.get('title', 'Primary outcome')}: HR {hr} ({ci_low}-{ci_high})"
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
        hr=hr,
        ci_low=ci_low,
        ci_high=ci_high,
        point=point,
        provenance=provenance,
    )
