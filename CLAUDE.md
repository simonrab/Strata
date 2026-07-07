# Living Meta-Analysis Tool: Build Context

## One-line pitch
A living meta-analysis tool that finds the trials, extracts the evidence with full provenance, and pools it into a current, auditable answer to a clinical question that updates itself as new results land.

## Outcome
The user asks a clinical question in PICO form for one outcome. The tool returns a single pooled answer: an effect estimate with confidence interval, a forest plot, heterogeneity measures, and a plain-language summary. Every number is traceable to its source trial and snippet. When a new trial reads out, the tool re-runs and flags whether the estimate or the conclusion changed, so the evidence base never goes stale.

## ICP
Medical affairs, HEOR, and clinical development teams who depend on meta-analyses to make evidence-based decisions. Their pain is concrete. A meta-analysis is out of date the moment it publishes, and refreshing it is slow, manual, and expensive. This tool gives them a current answer that can be traced and checked line by line, which is what makes it usable in a regulated setting rather than only interesting.

## Builder track fit
The Builder track rewards tools life sciences professionals actually need, built with Claude Code. This is a working tool built as an MCP server so Claude drives the full workflow. It also shows judgment about where to use a model and where not to. Claude reads and structures the evidence. Deterministic statistics do the pooling. That division is the trust story a life sciences tool has to earn.

## Core design principle
Divide the labour by what each part is reliable at.
- Claude reads and structures evidence. It is strong at reading, weak at arithmetic.
- A validated statistics library does all pooling and math. Never let the model compute pooled estimates.
- Every number is traceable to a source trial and the exact snippet it came from.
- The tool abstains rather than inventing precision when data is thin or heterogeneity is high.

## Engineering practice: TDD and BDD (mandatory)
All code, backend and frontend, is written test-first. No production module before its failing test.
- TDD: red, green, refactor. Write a failing test, make it pass, then clean up.
- BDD: describe behaviour as Given/When/Then scenarios that become executable tests. Cover the pipeline spine and user journeys this way.
- Backend: `pytest` plus `pytest-bdd` for Gherkin `.feature` scenarios. Frontend: Vitest plus React Testing Library, with BDD scenarios for the ask, run, and report journeys.
- The deterministic validation gate and the stats engine get the heaviest coverage. They are the trust story.

## Architecture
Build as an MCP server so Claude can drive the workflow, plus a fully functioning web UI platform that runs the whole review end to end: ask a question, watch the pipeline execute, inspect the evidence ledger, verify extractions, review risk of bias and GRADE, and read the report with its forest plot. The UI is a first-class deliverable, not a demo shim. The screens in `stitch_livemeta_precision_evidence_system/` are the reference design to build against.

MCP tools:
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
3. Extract effect data into a fixed schema. Binary outcomes: events and totals per arm. Continuous outcomes: mean, SD, n per arm. Every value carries the source trial ID and source snippet.
4. Validate deterministically before any pooling.
5. Assess risk of bias per trial with RoB 2, and rate certainty of evidence with GRADE (see Risk of bias and certainty below). Claude does a first-pass reading, a human confirms.
6. Pool with a validated library. Compute pooled effect, confidence interval, I-squared, tau-squared.
7. Output a forest plot, a plain-language summary, heterogeneity warnings, and a leave-one-out sensitivity check.
8. Living layer: when a new trial lands, re-run and flag whether the estimate or conclusion changed.

## Extraction strategy
Safety-first tiering. Fail safely on the messy tail rather than pool bad numbers.
- Take structured arm-level results from ClinicalTrials.gov v2 first. Drop to full text only for trials whose effect data is not in a structured field.
- In full text, parse tables as tables rather than flattening the PDF into one text blob. Most effect data sits in tables.
- Require provenance. Each value carries its source trial ID and the exact sentence or table cell. If a value is not clearly present, return null and flag the trial. No silent inference or back-calculation.
- Low-confidence or conflicting extractions surface for quick human review before entering the pool. This is the audit trail, not a workaround.

## Statistics: Cochrane-aligned method
Follow the Cochrane Handbook for Systematic Reviews of Interventions, v6.5, Chapter 10 (updated November 2024). Use a validated meta-analysis library, never hand-rolled pooling. If a required method is not available in the library, flag the case rather than substitute a biased default.

Homogeneity gate before any pooling.
- Only pool studies judged similar enough in population, intervention, comparator, and outcome to give a clinically meaningful answer. This is a mandatory Cochrane expectation, not optional. Surface clinical diversity and require confirmation rather than silently combining unlike trials.

Core method.
- Two-stage inverse-variance approach. Compute a per-study effect and standard error, then a weighted average.
- Pool ratio measures (risk ratio, odds ratio) on the log scale.

Effect measure selection.
- Binary outcomes: prefer risk ratio or odds ratio. Avoid risk difference, which is less consistent.
- Continuous outcomes: mean difference when studies share a scale, standardized mean difference when scales differ. Assumes approximate normality, so check for skew. Do not mix log-transformed and untransformed data.

Model and variance estimator.
- Default to random-effects.
- Use REML for the between-study variance (Tau-squared), the Cochrane default since 2024. DerSimonian-Laird is an available alternative.
- Never choose fixed versus random effects based on a heterogeneity test.

Confidence interval.
- Use the Hartung-Knapp-Sidik-Jonkman (HKSJ) interval with a t-distribution when Tau-squared is above zero and there are more than two studies.
- Use the Wald-type interval otherwise. Flag that HKSJ can be too wide with only two or three studies and Wald can be too narrow.

Heterogeneity reporting.
- Report the Chi-squared test read at P below 0.10 (it is underpowered), I-squared with interpretation bands, and Tau-squared.
- Interpretation bands for I-squared: 0 to 40 percent might not be important, 30 to 60 moderate, 50 to 90 substantial, 75 to 100 considerable. Avoid rigid thresholds, especially with few studies.
- Add a prediction interval when there are five or more studies and no clear funnel plot asymmetry.

Rare events.
- Inverse-variance and DerSimonian-Laird are biased when events are rare. Below roughly 1 percent event rates, or when many study arms have zero events, switch to Peto or Mantel-Haenszel without zero-cell correction, or flag rather than pool.
- Exclude studies with no events in both arms. Do not apply fixed 0.5 zero-cell corrections silently, as they bias estimates.

Sensitivity analysis.
- Run leave-one-out.
- With only two or three studies, compare Wald and HKSJ intervals and report the difference rather than hiding it.

Data conversions.
- Standard-form conversions such as SE to SD or CI to SD use Cochrane Handbook formulas, run in code, with each conversion logged as an assumption.

Out of scope for the hackathon (statistical).
- Subgroup analysis and meta-regression. Meta-regression needs about ten studies to be meaningful.
- Network meta-analysis and time-to-event reconstruction.

## Risk of bias and certainty (RoB 2 and GRADE)
These are core credibility steps, not preamble. Pooling numbers from trials that were never appraised produces a confident wrong answer. Each step is split by the core principle: Claude reads and judges, code computes what it can, a human confirms the load-bearing calls.

Risk of bias (RoB 2), per trial.
- Assess the five RoB 2 domains: randomization, deviations from intended interventions, missing outcome data, measurement of the outcome, and selection of the reported result.
- Claude does a first-pass judgment per domain with a source quote for each; a human confirms. Every judgment carries its provenance, same as an extracted number.
- This gate feeds two things downstream: a sensitivity analysis restricted to low-risk-of-bias trials, and the risk-of-bias input to GRADE.

Certainty of evidence (GRADE).
- Rate certainty per outcome as high, moderate, low, or very low, and output a Summary-of-Findings line.
- Much of it is derivable from what we already compute: inconsistency from I-squared, imprecision from confidence-interval width and event counts, plus risk of bias from RoB 2. Claude judges indirectness and publication bias. Record the rationale for any downgrade.

## Deterministic validation gate
Plain code, not the model, runs these before pooling.
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
- Meta-analysis library: check `pymare` first for REML support, with R `metafor` via `rpy2` as the fallback if REML or HKSJ are missing. `statsmodels.stats.meta_analysis` covers DerSimonian-Laird. Do not hand-roll pooling. `scipy` and `numpy` for support.
- `matplotlib` for the forest plot.
- `httpx` or `requests` for the ClinicalTrials.gov and Europe PMC APIs.
- A fully functioning web UI platform for the front end, built against the reference designs in `stitch_livemeta_precision_evidence_system/`.

## Demo plan
- Pick a clinical question where the answer is already well established, so judges can sanity-check the output against known truth. [DECISION NEEDED: lock the exact question.]
- Scope to one question, one outcome type, five to ten trials from structured results.
- Memorable moment: inject an additional trial live and watch the pooled estimate and conclusion update.

## Main risks and mitigations
- Extraction errors: prefer structured results over free text, require provenance, validate before pooling.
- Wrong pooling: use a validated library, never model math.
- Scope creep: lock to one question and one outcome.
