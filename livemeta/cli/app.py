"""The `livemeta` CLI: argparse surface + handlers over the shared pipeline core.

A one-shot process, so dependencies are keyword-injected into `main` rather than
held on a long-lived server object — that keeps each invocation hermetic under
tests (pass `fetch_study=`/`store=`) and lets `main` return an int exit code the
caller `sys.exit`s. Every handler delegates to `livemeta.core` (the same
functions the FastAPI app and MCP server call) and to the pure renderers in
`render.py`; the exact decision→repool→snapshot sequences mirror
`livemeta/api/app.py`.

Exit codes: 0 success (pool produced / read succeeded); 2 argparse usage error;
3 internal error; 4 honest abstention (ran, but no pooled estimate); 5 unknown
question id.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Load local .env (DATABASE_URL, ANTHROPIC_API_KEY) like the web app does, so an
# interactive CLI picks up the same secrets. Skipped under pytest, which wires
# its stores explicitly and must stay network-free.
if "pytest" not in sys.modules:  # pragma: no cover - exercised only outside tests
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

from . import render

EXIT_OK = 0
EXIT_ABSTAINED = 4
EXIT_NOT_FOUND = 5
EXIT_INTERNAL = 3


# --- dependency resolution --------------------------------------------------


def _resolve_store(args, store):
    """Injected store wins (tests); else --data-dir forces a local SQLite store,
    bypassing make_store()'s Postgres branch so a stray DATABASE_URL can't
    redirect a local run; else make_store() picks the deployed backend."""
    if store is not None:
        return store
    from ..core.store import SnapshotStore, make_store

    if getattr(args, "data_dir", None):
        return SnapshotStore(args.data_dir)
    return make_store()


def _fixture_fetch(directory: str):
    base = Path(directory)

    def fetch(nct_id: str) -> dict:
        return json.loads((base / f"{nct_id}.json").read_text())

    return fetch


def _resolve_fetch(args, fetch_study):
    """Injected fetch wins (tests); else --fixtures reads recorded CT.gov JSON for
    a network-free run; else the live multi-source router."""
    if fetch_study is not None:
        return fetch_study
    if getattr(args, "fixtures", None):
        return _fixture_fetch(args.fixtures)
    from ..core.sources.router import SourceRouter

    return SourceRouter().fetch


def _resolve_search(args, search_client):
    if search_client is not None:
        return search_client
    from ..core.sources.clinicaltrials import ClinicalTrialsClient

    return ClinicalTrialsClient()


def _resolve_parse(args, parse):
    if parse is not None:
        return parse
    from ..core import llm
    from ..core.sources.clinicaltrials import ClinicalTrialsClient
    from ..core.sources.europepmc import EuropePmcClient

    def _parse(text: str):
        return llm.parse_question(
            text, search_client=ClinicalTrialsClient(), epmc_client=EuropePmcClient()
        )

    return _parse


# --- output helpers ---------------------------------------------------------


def _out(text: str) -> None:
    print(text)


def _err(text: str) -> None:
    print(text, file=sys.stderr)


def _emit_json(model) -> None:
    """A single machine-readable JSON document on stdout."""
    if isinstance(model, list):
        print("[" + ",".join(m.model_dump_json() for m in model) + "]")
    else:
        print(model.model_dump_json())


def _emit_review(result, args, *, plot_pool=True) -> int:
    """Print a ReviewResult as JSON or a rendered report (+ optional PNG)."""
    if args.json:
        _emit_json(result)
    else:
        _out(render.report_text(result))
    if plot_pool and getattr(args, "plot", None):
        if result.pool is None:
            _err("No pooled estimate to plot — skipping --plot.")
        else:
            from . import plot as plot_mod

            plot_mod.write_forest_png(result.pool, args.plot)
            _err(f"Wrote forest plot to {args.plot}")
    return EXIT_OK if result.pool is not None else EXIT_ABSTAINED


# --- handlers ---------------------------------------------------------------


def _cmd_run(args, *, store, fetch_study, parse, search_client) -> int:
    from ..core import pipeline
    from ..core import search as search_mod
    from ..core.schema import ReviewResult

    if not args.question_text:
        _err("run needs --question-text TEXT.")
        return EXIT_INTERNAL
    question = parse(args.question_text)
    # A question with no trial_ids is discovered live through the injected search
    # client; one that already carries candidates skips straight to extraction.
    search_fn = lambda pico: [
        c.nct_id for c in search_mod.search_trials(pico, client=search_client)
    ]

    final: ReviewResult | None = None
    for event in pipeline.run_review(question, fetch_study, search_fn=search_fn):
        if not args.quiet and not args.json:
            _err(render.progress_line(event))
        if event.stage == "done" and event.data is not None:
            final = ReviewResult.model_validate(event.data)

    if final is None:
        _err("Pipeline produced no terminal result.")
        return EXIT_INTERNAL

    if not args.no_save:
        store.save_snapshot(final)
    return _emit_review(final, args)


def _cmd_search(args, *, search_client) -> int:
    from ..core import search as search_mod
    from ..core.schema import PICO

    pico = PICO(
        population=args.population or "",
        intervention=args.intervention,
        comparator=args.comparator or "",
        outcome=args.outcome,
    )
    candidates = search_mod.search_trials(
        pico, max_results=args.max, client=search_client
    )
    if args.json:
        _emit_json(candidates)
    else:
        _out(render.candidates_table(candidates))
    return EXIT_OK


def _cmd_report(args, *, store) -> int:
    if args.version is not None:
        result = store.load_version(args.question_id, args.version)
    else:
        result = store.load_latest(args.question_id)
    if result is None:
        _err(f"No such review/snapshot: {args.question_id}.")
        return EXIT_NOT_FOUND
    _emit_review(result, args)
    return EXIT_OK  # a successful read is exit 0 even if the saved run abstained


def _cmd_history(args, *, store) -> int:
    snaps = store.list_snapshots(args.question_id)
    if not snaps and store.load_latest(args.question_id) is None:
        _err(f"No such review: {args.question_id}.")
        return EXIT_NOT_FOUND
    if args.json:
        _emit_json(snaps)
    else:
        _out(render.history_table(snaps))
    return EXIT_OK


def _cmd_list(args, *, store) -> int:
    from ..core.diff import diff_reviews, status_from_diff
    from ..core.schema import ReviewSummary

    summaries: list[ReviewSummary] = []
    for qid in store.list_questions():
        latest = store.load_latest(qid)
        if latest is None:
            continue
        versions = store.list_versions(qid)
        status = "unchanged"
        if len(versions) >= 2:
            previous = store.load_version(qid, versions[-2])
            if previous is not None:
                status = status_from_diff(
                    diff_reviews(
                        previous, latest,
                        previous_version=versions[-2], current_version=versions[-1],
                    )
                )
        pool = latest.pool
        summaries.append(
            ReviewSummary(
                question_id=qid,
                text=latest.question.text,
                versions=len(versions),
                k=pool.k if pool else 0,
                estimate=pool.estimate if pool else None,
                ci_low=pool.ci_low if pool else None,
                ci_high=pool.ci_high if pool else None,
                measure=latest.question.measure.value,
                status=status,
            )
        )
    if args.json:
        _emit_json(summaries)
    else:
        _out(render.reviews_table(summaries))
    return EXIT_OK


def _cmd_update(args, *, store, fetch_study) -> int:
    from ..core import living
    from ..core.diff import status_from_diff

    try:
        diff = living.apply_update(
            store, args.question_id, args.new_trial_id, fetch_study
        )
    except ValueError:
        _err(f"No such review: {args.question_id}. Run one first.")
        return EXIT_NOT_FOUND
    if args.json:
        _emit_json(diff)
    else:
        _out(render.diff_block(diff, status_from_diff(diff)))
    return EXIT_OK


def _cmd_check_updates(args, *, store, search_client) -> int:
    from ..core import living

    try:
        candidates = living.check_for_new_trials(
            store, args.question_id, search_client
        )
    except ValueError:
        _err(f"No such review: {args.question_id}. Run one first.")
        return EXIT_NOT_FOUND
    if args.json:
        _emit_json(candidates)
    else:
        _out(render.candidates_table(candidates))
    return EXIT_OK


def _cmd_decision(args, *, store) -> int:
    from ..core import pipeline
    from ..core.schema import ReviewDecision

    latest = store.load_latest(args.question_id)
    if latest is None:
        _err(f"No such review: {args.question_id}.")
        return EXIT_NOT_FOUND
    store.save_decision(
        args.question_id,
        ReviewDecision(study_id=args.study_id, decision=args.decision, reason=args.reason),
    )
    repooled = pipeline.repool_with_decisions(
        latest, store.load_decisions(args.question_id)
    )
    store.save_snapshot(repooled)
    _emit_review(repooled, args)
    return EXIT_OK


def _cmd_diversity_confirm(args, *, store) -> int:
    from ..core import pipeline
    from ..core.schema import DiversityDecision

    latest = store.load_latest(args.question_id)
    if latest is None:
        _err(f"No such review: {args.question_id}.")
        return EXIT_NOT_FOUND
    confirmed = pipeline.repool_with_diversity(
        latest, DiversityDecision(reason=args.reason)
    )
    store.save_snapshot(confirmed)
    _emit_review(confirmed, args)
    return EXIT_OK


def _cmd_rob_decision(args, *, store) -> int:
    from ..core import rob as rob_mod
    from ..core.schema import RobDecision

    latest = store.load_latest(args.question_id)
    if latest is None:
        _err(f"No such review: {args.question_id}.")
        return EXIT_NOT_FOUND
    store.save_rob_decision(
        args.question_id,
        RobDecision(study_id=args.study_id, domain_key=args.domain_key, reason=args.reason),
    )
    decisions = store.load_rob_decisions(args.question_id)
    latest.rob = [rob_mod.apply_rob_decisions(a, decisions) for a in latest.rob]
    store.save_snapshot(latest)
    _emit_review(latest, args)
    return EXIT_OK


def _cmd_screening_decision(args, *, store, fetch_study) -> int:
    from ..core import pipeline, rob as rob_mod
    from ..core.schema import EligibilityDecision

    latest = store.load_latest(args.question_id)
    if latest is None:
        _err(f"No such review: {args.question_id}.")
        return EXIT_NOT_FOUND
    store.save_screening_decision(
        args.question_id,
        EligibilityDecision(
            study_id=args.study_id,
            decision=args.decision,
            reason=args.reason or "Reviewer sign-off.",
            by_claude=False,
            confirmed=True,
        ),
    )
    overrides = {
        d.study_id: d for d in store.load_screening_decisions(args.question_id)
    }
    rerun = pipeline.run_review_collect(
        latest.question, fetch_study, screening_overrides=overrides
    )
    review_decisions = store.load_decisions(args.question_id)
    if review_decisions:
        rerun = pipeline.repool_with_decisions(rerun, review_decisions)
    rob_decisions = store.load_rob_decisions(args.question_id)
    if rob_decisions:
        rerun.rob = [rob_mod.apply_rob_decisions(a, rob_decisions) for a in rerun.rob]
    store.save_snapshot(rerun)
    _emit_review(rerun, args)
    return EXIT_OK


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--data-dir", help="Local SQLite store dir (bypasses DATABASE_URL).")
    parent.add_argument("--json", action="store_true", help="Emit a JSON document on stdout.")
    parent.add_argument("--offline", action="store_true", help="Do not hit the network.")
    parent.add_argument("--fixtures", help="Read CT.gov JSON from DIR (implies --offline).")
    parent.add_argument("--quiet", action="store_true", help="Suppress progress on stderr.")

    parser = argparse.ArgumentParser(
        prog="livemeta",
        description="Living meta-analysis over the shared pipeline core, from the terminal.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", parents=[parent], help="Run a review end to end.")
    p_run.add_argument("--question-text", help="Free-text clinical question to parse and run.")
    p_run.add_argument("--plot", help="Also write a matplotlib forest-plot PNG to this path.")
    p_run.add_argument("--no-save", action="store_true", help="Do not persist a snapshot.")

    p_search = sub.add_parser("search", parents=[parent], help="Search candidate trials for a PICO.")
    p_search.add_argument("--population", default="")
    p_search.add_argument("--intervention", required=True)
    p_search.add_argument("--comparator", default="")
    p_search.add_argument("--outcome", required=True)
    p_search.add_argument("--max", type=int, default=1000)

    p_report = sub.add_parser("report", parents=[parent], help="Show a saved review's report.")
    p_report.add_argument("question_id")
    p_report.add_argument("--version", type=int, help="A specific version (default: latest).")
    p_report.add_argument("--plot", help="Write a matplotlib forest-plot PNG to this path.")

    p_hist = sub.add_parser("history", parents=[parent], help="Show a review's version timeline.")
    p_hist.add_argument("question_id")

    sub.add_parser("list", parents=[parent], help="List all saved reviews.")

    p_update = sub.add_parser("update", parents=[parent], help="Add a trial, re-run, and diff.")
    p_update.add_argument("question_id")
    p_update.add_argument("new_trial_id")

    p_check = sub.add_parser("check-updates", parents=[parent], help="Re-search for genuinely new trials.")
    p_check.add_argument("question_id")

    p_dec = sub.add_parser("decision", parents=[parent], help="Confirm/flag a trial's extraction and re-pool.")
    p_dec.add_argument("question_id")
    p_dec.add_argument("study_id")
    p_dec.add_argument("decision", choices=["confirmed", "flagged"])
    p_dec.add_argument("--reason")

    p_div = sub.add_parser("diversity-confirm", parents=[parent], help="Lift the homogeneity gate and pool.")
    p_div.add_argument("question_id")
    p_div.add_argument("--reason")

    p_rob = sub.add_parser("rob-decision", parents=[parent], help="Sign off one RoB 2 domain.")
    p_rob.add_argument("question_id")
    p_rob.add_argument("study_id")
    p_rob.add_argument("domain_key")
    p_rob.add_argument("--reason")

    p_scr = sub.add_parser("screening-decision", parents=[parent], help="Include/exclude a trial and re-run.")
    p_scr.add_argument("question_id")
    p_scr.add_argument("study_id")
    p_scr.add_argument("decision", choices=["included", "excluded"])
    p_scr.add_argument("--reason")

    return parser


def main(argv=None, *, fetch_study=None, store=None, search_client=None, parse=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            return _cmd_run(
                args,
                store=_resolve_store(args, store),
                fetch_study=_resolve_fetch(args, fetch_study),
                parse=_resolve_parse(args, parse),
                search_client=_resolve_search(args, search_client),
            )
        if args.command == "search":
            return _cmd_search(args, search_client=_resolve_search(args, search_client))
        if args.command == "report":
            return _cmd_report(args, store=_resolve_store(args, store))
        if args.command == "history":
            return _cmd_history(args, store=_resolve_store(args, store))
        if args.command == "list":
            return _cmd_list(args, store=_resolve_store(args, store))
        if args.command == "update":
            return _cmd_update(
                args,
                store=_resolve_store(args, store),
                fetch_study=_resolve_fetch(args, fetch_study),
            )
        if args.command == "check-updates":
            return _cmd_check_updates(
                args,
                store=_resolve_store(args, store),
                search_client=_resolve_search(args, search_client),
            )
        if args.command == "decision":
            return _cmd_decision(args, store=_resolve_store(args, store))
        if args.command == "diversity-confirm":
            return _cmd_diversity_confirm(args, store=_resolve_store(args, store))
        if args.command == "rob-decision":
            return _cmd_rob_decision(args, store=_resolve_store(args, store))
        if args.command == "screening-decision":
            return _cmd_screening_decision(
                args,
                store=_resolve_store(args, store),
                fetch_study=_resolve_fetch(args, fetch_study),
            )
    except BrokenPipeError:  # pragma: no cover - piping into head/less
        return EXIT_OK

    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
