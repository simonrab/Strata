# Living Meta-Analysis Tool: Build Context

## Goal
Build a tool that answers a clinical question with a live, auditable meta-analysis. Given a question in PICO form and one outcome, it finds the relevant randomised trials, extracts effect data with full provenance, pools it with proper random-effects statistics, and returns a forest plot with heterogeneity measures. When a new trial appears, it re-runs and flags whether the pooled estimate or the conclusion changed.

## Why
Meta-analyses go stale the moment they publish, and redoing them is slow and expensive. A living version that keeps rigour and shows its working is a real need for medical affairs, HEOR, and clinical development teams. The differentiator is trust: every number is traceable and the statistics are deterministic.

## Core design principle
Divide the labour by what each part is reliable at.
- Claude reads and structures evidence. It is strong at reading, weak at arithmetic.
- A validated statistics library does all pooling and math. Never let the model compute pooled estimates.
- Every number is traceable to a source trial and the exact snippet it came from.
- The tool abstains rather than inventing precision when data is thin or heterogeneity is high.

## Architecture
Build as an MCP server so Claude can drive the full workflow, plus a thin UI or CLI that renders the forest plot.

MCP tools to expose:
- `search_trials(pico, outcome)`: find candidate trials.
- `extract_effects(trial_id)`: return structured effect data with provenance.
- `validate(extractions)`: run deterministic checks, return pass or flag.
- `pool(validated_effects)`: run random-effects meta-analysis, return estimate and stats.
- `update(question_id, new_trial)`: re-run and diff against the previous result.

## Data sources
- ClinicalTrials.gov v2 API (https://clinicaltrials.gov/data-api/api). Primary source. Returns structured arm-level results, which avoids PDF parsing.
- Europe PMC REST API (https://europepmc.org/RestfulWebService) or PubMed. For published trials and abstracts.
- Full text only when structured effect data is absent.

## Pipeline
1. Parse the question into PICO and one outcome. Claude does this.
2. Retrieve candidate trials from ClinicalTrials.gov v2 first, supplemented by Europe PMC.
3. Extract effect data into a fixed schema. Binary outcomes: events and totals per arm. Continuous outcomes: mean, SD, n per arm. Every value carries the source trial ID and the source snippet.
4. Validate deterministically before any pooling.
5. Pool with a validated library. Compute pooled effect, confidence interval, I-squared, tau-squared.
6. Output a forest plot, a plain-language summary, heterogeneity warnings, and a leave-one-out sensitivity check.
7. Living layer: when a new trial lands, re-run and flag whether the estimate or conclusion changed.

## Full systematic review scope (Cochrane Handbook Part 2)
The meta-analysis is Chapter 10 — one step of a fifteen-chapter review process (https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/part-2). Pooling numbers from trials that were selected loosely, extracted carelessly, or never appraised for bias produces a confident wrong answer. So the tool is a **living systematic review with meta-analysis at its core**, and the steps that feed the pool are first-class, not preamble. Each step is split by the core principle — Claude reads and judges, code computes, a human confirms the load-bearing calls.

Pipeline (chapter → step → who):
- Ch2 — scope the question into PICO + one outcome — Claude.
- Ch3 — set explicit eligibility criteria — Claude, human confirms.
- Ch4 — search and select trials; keep PRISMA-style counts and per-trial exclusion reasons — code retrieves, Claude screens.
- Ch5 — collect arm-level data with provenance — code parses, Claude maps ambiguous fields.
- Ch6 — compute per-trial effect estimates — code.
- **Ch7-8 — assess risk of bias (RoB 2) across the five domains, per trial** — Claude does a first-pass reading, human confirms. This is the credibility gate the pool depends on, and it feeds both sensitivity analysis (restrict to low risk of bias) and GRADE. Do not skip it.
- Ch9 — prepare for synthesis: group only comparable trials, flag unit-of-analysis problems — code + Claude.
- Ch10 — the meta-analysis (see Statistics and Full meta-analysis scope).
- **Ch13-14 — rate certainty of evidence (GRADE) and check reporting bias** — much of it is derivable from what we already compute: inconsistency from I-squared, imprecision from CI width and event counts, plus risk of bias from Ch7-8; Claude judges indirectness. Output a Summary-of-Findings line with a certainty rating (high/moderate/low/very low).
- Ch15 — interpret and conclude in plain language with caveats — Claude drafts, human signs off.

Risk of bias (Ch7-8) and GRADE certainty (Ch14) are the two additions that turn "a pooled number with a plot" into "a defensible answer." Treat them as core for credibility even though they sit outside the arithmetic. Network meta-analysis (Ch11) and non-standard synthesis (Ch12) are out of scope.

## Extraction strategy
Safety-first tiering. Fail safely on the messy tail rather than pool bad numbers.
- Take structured arm-level results from ClinicalTrials.gov v2 first. Drop to full text only for trials whose effect data is not in a structured field.
- In full text, parse tables as tables rather than flattening the PDF into one text blob. Most effect data sits in tables.
- Require provenance. Each value carries its source trial ID and the exact sentence or table cell. If a value is not clearly present, return null and flag the trial. No silent inference or back-calculation.
- Low-confidence or conflicting extractions surface for quick human review before entering the pool. This is the audit trail, not a workaround.

## Statistics
- Use a validated library, not hand-rolled math. Python `statsmodels.stats.meta_analysis` (`combine_effects`) for inverse-variance random-effects pooling.
- Report pooled effect, 95% confidence interval, I-squared, tau-squared, Cochran's Q with p-value, and a **prediction interval** (the range of true effects across settings — distinct from the CI of the mean, and routinely omitted by tools that stop at the forest plot).
- Choose the pooling method to fit the data, and state which was used and why: Mantel-Haenszel for sparse dichotomous data, Peto for rare events, generic inverse-variance otherwise. Handle zero cells explicitly (continuity correction or a method that avoids it), logged as an assumption.
- Choose the effect measure to fit the outcome: risk ratio / odds ratio / risk difference (dichotomous), mean difference / standardized mean difference (continuous).
- Random-effects estimator is a choice, not a default: DerSimonian-Laird or REML for tau-squared, and apply the Hartung-Knapp-Sidik-Jonkman adjustment when studies are few (DL under-covers with a handful of trials).
- Sensitivity suite, not a single number: leave-one-out, fixed-effect vs random-effect comparison, and robustness to inclusion/exclusion decisions.
- Convert to absolute effects (apply the pooled relative effect to a baseline risk) so the plain-language summary is interpretable, not just a ratio.
- Flag unit-of-analysis problems before pooling: multi-arm trials sharing a control arm (double-counting), cluster trials, repeated measurements.
- Standard-form conversions such as SE to SD or CI to SD use Cochrane Handbook formulas, run in code, and each conversion is logged as an assumption.

## Full meta-analysis scope (Cochrane Handbook Chapter 10)
The forest plot is one figure; the deliverable is a meta-analysis, and Chapter 10 (https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-10) defines what that means. Scope the build in tiers.

Core (must be present for it to count as a real meta-analysis, and all achievable for the constrained case of dichotomous outcomes from RCTs):
- Appropriate effect measure and pooling method, stated and justified (see Statistics above).
- Full heterogeneity panel: Q + p, I-squared, tau-squared, and a prediction interval.
- Sensitivity analyses: leave-one-out and fixed-vs-random comparison.
- Absolute-effect translation from a stated baseline risk.
- Unit-of-analysis checks and the exclusion/assumption audit trail.
- Honest abstention when heterogeneity is high, studies are too few, or data is thin.

Extensions (clearly scoped, add if time allows):
- Continuous outcomes (MD/SMD), and mixed dichotomous+continuous via re-expression.
- Subgroup analysis and meta-regression to investigate heterogeneity.
- Small-study-effect / publication-bias checks (funnel plot, Egger) — strictly, Chapter 13.

Out of scope for the hackathon (detect and route to manual review, be honest about it):
- Time-to-event / hazard-ratio pooling that requires reconstructing data from Kaplan-Meier curves.
- Ordinal scales and count/rate (Poisson) outcomes.
- Bayesian meta-analysis.
- Individual-participant-data methods.

## Deterministic validation gate
Plain code, not the model, runs these before pooling:
- Events cannot exceed arm totals.
- Arm sizes must sum correctly.
- Percentages must match counts.
- Anything that fails is flagged for review, not pooled.

## Out of scope for the hackathon
- Digitising effect sizes from figures such as Kaplan-Meier curves.
- Reconstructing time-to-event data.
Detect when a trial only reports outcomes this way and route it to manual review. Be honest about what the tool cannot yet read.

## The rule that holds it together
Pool only numbers that can be traced to a source and pass validation. Report what was excluded and why. Refuse a confident pooled estimate when heterogeneity is high or data is thin.

## Tech stack
- Python.
- MCP Python SDK for the server.
- `statsmodels` for meta-analysis, `scipy` and `numpy` for support.
- `matplotlib` for the forest plot.
- `requests` or `httpx` for the ClinicalTrials.gov and Europe PMC APIs.
- Thin CLI or minimal web UI for the demo.

## Suggested build order
1. ClinicalTrials.gov v2 client returning structured arm-level results for a fixed query.
2. Extraction schema and `extract_effects` for structured results only.
3. Validation gate.
4. `pool` with statsmodels, returning estimate, CI, I-squared, tau-squared.
5. Forest plot rendering.
6. Full-text extraction path for trials missing structured data.
7. Living layer: `update` with a diff against the previous run.
8. Wrap as MCP tools and wire the CLI or UI.

## Demo plan
- Pick a clinical question where the answer is already well established, so judges can sanity-check the output against known truth.
- Scope to one question, one outcome type, five to ten trials from structured results.
- The memorable moment: inject an eleventh trial live and watch the pooled estimate and the conclusion update.

## Main risks and mitigations
- Extraction errors: prefer structured results over free text, require provenance, validate before pooling.
- Wrong pooling: use a validated library, never model math.
- Scope creep: lock to one question and one outcome.
