# Strata (Work in Progress)

Strata is a living meta-analysis tool. You ask a clinical question in PICO form, and it finds the trials, extracts the effect data, appraises it, and pools it into one answer: an effect estimate with a confidence interval, a forest plot, heterogeneity measures, and a plain-language summary. Every number links back to the trial and the snippet it came from. When a new trial reads out, Strata re-runs and tells you whether the estimate or the conclusion changed.

The problem it addresses is that a meta-analysis goes stale the day it publishes, and updating one by hand is slow and expensive.

Strata also rolls those pooled answers up into a market landscape: a board of assets by indication, stage, and time. Each cell is backed by the same pooled evidence, so the landscape shows who is ahead on the trial data rather than just who is running trials, and it stays current because the evidence underneath it does.

## How it divides the work

The design splits the pipeline by what each part is good at.

The LLM does the reading. It parses the question into PICO, pulls arm-level results out of trial records, and does a first-pass RoB 2 and GRADE read. It never does arithmetic on the results.

Deterministic code does the numbers. All pooling runs through a validated statistics library (random-effects, REML, HKSJ intervals). Before anything is pooled, a validation gate checks it: events can't exceed arm totals, arm sizes have to sum, percentages have to match counts. Whatever fails that check is flagged for review instead of pooled.

Two other rules fall out of this. Every extracted value and every risk-of-bias judgment carries its source trial ID and the exact sentence or table cell behind it. And when the data is thin or heterogeneity is high, Strata reports that it can't give a reliable estimate rather than producing a false-precise one.

## The pipeline

1. Parse the question into PICO and one outcome (the LLM).
2. Retrieve candidate trials from [ClinicalTrials.gov v2](https://clinicaltrials.gov/data-api/api). [PubMed / Europe PMC](https://europepmc.org/RestfulWebService) and [openFDA](https://open.fda.gov/) approvals are available as opt-in sources (off by default), named per request; PubMed records surface for review but never enter the pool, since only CT.gov's structured results are pooled.
3. Extract arm-level effect data into a fixed schema: events and totals per arm for binary outcomes, mean, SD, and n for continuous. There is no back-calculation. A missing value returns null and flags the trial.
4. Validate deterministically.
5. Appraise each trial with RoB 2 across its five domains, with a quote behind each judgment, and rate certainty with GRADE. The LLM reads first; a human confirms the calls that matter.
6. Pool: pooled effect, confidence interval, I², τ².
7. Report: forest plot, funnel plot with Egger's test, leave-one-out sensitivity check, PRISMA record-flow, and a plain-language summary with heterogeneity warnings.
8. Living layer: when a new trial lands, re-run, re-pool, and diff against the last version.

## Architecture

There are three front ends over one core:

- An MCP server (`livemeta/mcp/server.py`) exposing 25 tools, so Claude can drive the whole workflow over stdio.
- A web platform: a FastAPI backend (`livemeta/api/app.py`) serving a React and Vite front end (`web/`). It runs a review end to end: ask a question, watch the pipeline run, inspect the evidence ledger, verify extractions, review risk of bias and GRADE, read the report, and see the competitive-landscape board.
- A command-line interface (`livemeta/cli/`, the `livemeta` command). Full parity with the other two: run a review, read the report with an ASCII forest plot, search, list history, drive the living update, and record every human-in-the-loop decision — all scriptable and runnable fully offline against recorded fixtures.

The product is called Strata, but the codebase still uses the earlier `livemeta` name for the Python package, the `livemeta-mcp` command, and the `LIVEMETA_*` environment variables.

```
livemeta/
├── core/            # the engine
│   ├── search.py        # trial retrieval (CT.gov v2; opt-in Europe PMC)
│   ├── extract.py       # arm-level extraction with provenance
│   ├── validate.py      # deterministic validation gate
│   ├── homogeneity.py   # clinical-diversity gate before pooling
│   ├── stats/           # pooling engine (random-effects, REML, HKSJ)
│   ├── rob.py           # RoB 2 first-pass appraisal
│   ├── grade.py         # GRADE certainty rating
│   ├── prisma.py        # PRISMA record-flow
│   ├── living.py        # re-run + diff when a new trial lands
│   ├── diff.py          # version-to-version conclusion diff
│   ├── ci/              # competitive-intelligence landscape layer
│   ├── store.py         # snapshot store (SQLite)
│   └── store_pg.py      # Postgres store (deployed)
├── mcp/server.py    # 25 MCP tools
├── api/app.py       # FastAPI backend + websocket pipeline events
└── cli/             # the `livemeta` command line (argparse over the same core)

web/                 # React + TypeScript + Vite front end
tests/               # pytest + pytest-bdd (Gherkin .feature scenarios)
```

### The 25 MCP tools

| Group | Tools |
|---|---|
| Question & search | `parse_question`, `search_trials`, `search_publications` |
| Extract & pool | `extract_effects`, `validate`, `pool` |
| Appraisal | `assess_rob`, `grade_outcome` |
| Sensitivity & review | `leave_one_out`, `run_review`, `confirm_diversity`, `record_decision` |
| Living layer | `update`, `check_updates` |
| Competitive landscape | `map_landscape`, `track_asset`, `ingest_announcement`, `asset_dossier`, `indication_map`, `company_pipeline` |
| Market intelligence | `landscape_changes`, `milestone_radar`, `moa_landscape`, `compare_assets`, `market_ask` |

`search_trials`, `run_review`, and the market/company tools take an optional `sources` argument (comma list, e.g. `ctgov,pubmed,openfda`) to opt into PubMed discovery or openFDA approvals per call.

## Statistics

The method is standard random-effects meta-analysis, following the Cochrane Handbook for Systematic Reviews of Interventions.

- Two-stage inverse-variance approach; ratio measures (RR, OR, HR) pooled on the log scale.
- Random-effects by default, with REML for the between-study variance (τ²).
- HKSJ interval with a t-distribution when τ² > 0 and there are more than two studies; Wald-type otherwise, with a note on when each can mislead.
- Heterogeneity: χ² read at P < 0.10, I² with interpretation bands, τ². Prediction interval when there are 5 or more studies and no funnel asymmetry.
- Rare events: below roughly 1% event rates, or with many zero-event arms, switch to Peto or Mantel-Haenszel without silent zero-cell correction, or flag rather than pool.
- Homogeneity gate: only pool studies similar enough in population, intervention, comparator, and outcome. Clinical diversity is surfaced and has to be confirmed.

Pooling runs on [`pymare`](https://github.com/neurostuff/PyMARE) for REML, with an R [`metafor`](https://www.metafor-project.org/) bridge as a fallback and `statsmodels` for DerSimonian-Laird. None of it is hand-rolled. Pick the engine with `LIVEMETA_STATS_ENGINE` (`auto`, `metafor`, or `python`).

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js (for the web front end)
- Optional: R with the `metafor` package. The Python engine is used automatically if it is absent.

### Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

npm --prefix web install
```

### Configure

Create a `.env` file. Everything is optional for a first run; without an LLM key the LLM steps return a PENDING state rather than failing.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the LLM's reading and extraction steps. Without it, those steps return PENDING. |
| `DATABASE_URL` | Postgres connection for the deployed snapshot store. Omit to use the local SQLite store. |
| `CTGOV_API_BASE` | Override the ClinicalTrials.gov base URL, e.g. to route through a proxy. |
| `LIVEMETA_STATS_ENGINE` | `auto` (default), `metafor`, or `python`. |
| `LIVEMETA_LLM_MODEL` | Override the model used for reading. |
| `LIVEMETA_DATA_DIR` | Directory for local snapshot storage. |


https://livemeta-backend-production.up.railway.app/

### Run the web platform locally

```bash
# Terminal 1: backend on :8000
./run-local.sh

# Terminal 2: front end on :5173
npm --prefix web run dev
```

Then open http://localhost:5173.

### Run the MCP server

```bash
livemeta-mcp        # stdio transport, for an MCP client such as Claude
```

Register it with an MCP client (for example, Claude Code):

```json
{
  "mcpServers": {
    "strata": { "command": "livemeta-mcp" }
  }
}
```

### Run from the command line

The `livemeta` command runs the whole review from the terminal over the same core as the web app and the MCP server. It works fully offline against the recorded CT.gov fixtures — pass `--fixtures tests/fixtures` (which implies `--offline`) so no run touches the network.

```bash
# Run the GLP-1/MACE question and read the report (with an ASCII forest plot).
# The run prints the question id it saved under; use that id in the commands below.
livemeta run --question-text "GLP-1 receptor agonists vs placebo for 3-point MACE" --fixtures tests/fixtures

# Opt in to PubMed discovery (records surface for review, never enter the pool)
livemeta run --question-text "GLP-1 receptor agonists vs placebo for 3-point MACE" --enable-pubmed

# Inject another trial into a saved review and see the conclusion diff
livemeta update glp1-mace NCT03496298 --fixtures tests/fixtures

# Read a saved review and also write a matplotlib forest-plot PNG
livemeta report glp1-mace --plot forest.png

# Human-in-the-loop: flag a trial's extraction and re-pool; confirm a RoB domain
livemeta decision glp1-mace NCT01147250 flagged --reason "unclear arm"
livemeta rob-decision glp1-mace NCT01179048 D1

# Machine-readable output for scripting (a single JSON document on stdout)
livemeta run --question-text "GLP-1 receptor agonists vs placebo for 3-point MACE" --fixtures tests/fixtures --json | python -m json.tool
```

Every subcommand accepts `--json`. Discovery is ClinicalTrials.gov by default; `--enable-pubmed` widens it to Europe PMC (opt-in). Exit codes are scriptable: `0` success (a pooled estimate was produced or a read succeeded), `4` honest abstention (the run completed but the data was too thin or too heterogeneous to pool), and `5` for an unknown review. Without `ANTHROPIC_API_KEY`, the LLM steps are reported as PENDING rather than fabricated, exactly as in the web app. Run `livemeta --help` for the full command list.

## Testing

The code is written test-first, with pytest-bdd scenarios for the pipeline spine and the main user journeys. The validation gate and the stats engine have the heaviest coverage.

```bash
pytest                       # backend: pytest + pytest-bdd
npm --prefix web run test    # frontend: Vitest + React Testing Library
```

Feature files are in `tests/features/` (pipeline, homogeneity, appraisal, human review, living update, MCP update, CLI).

## Scope

In scope: structured arm-level results; RoB 2 and GRADE appraisal; random-effects pooling with sensitivity checks; the living re-run and diff; the competitive landscape.

Out of scope for now: reading effect sizes off figures such as Kaplan-Meier curves, time-to-event reconstruction, subgroup analysis, meta-regression, and network meta-analysis. When a trial only reports an outcome in a form the tool can't read, it routes it to manual review instead of guessing.

