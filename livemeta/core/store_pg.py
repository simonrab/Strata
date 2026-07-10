"""Postgres snapshot store — the deployed backend (Supabase).

A drop-in for the SQLite `SnapshotStore` with the identical public interface, so
every caller and the whole test contract are unchanged; only the placeholder
style (%s), the upsert dialect, and the connection are Postgres-flavoured. Chosen
at runtime by `make_store()` when `DATABASE_URL` is set. A fresh connection per
call mirrors the SQLite store and keeps the WebSocket worker-thread path safe.

`result_json` is stored as `text` (not `jsonb`): the headline pool numbers are
denormalised into their own columns, so nothing ever queries inside the blob.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from .ci.schema import DevelopmentEvent, RegulatoryApproval, SubPopulation
from .schema import ReviewDecision, ReviewResult, RobDecision, SnapshotMeta


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PostgresSnapshotStore:
    def __init__(self, dsn: str | None = None, schema: str | None = None):
        self._dsn = dsn or os.environ["DATABASE_URL"]
        # A quoted, validated identifier — tests pass a generated schema name.
        self._schema = schema or "public"
        if not self._schema.replace("_", "").isalnum():
            raise ValueError(f"invalid schema name {self._schema!r}")
        self._init_db()

    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn, row_factory=dict_row, autocommit=True)
        conn.execute(f'SET search_path TO "{self._schema}"')
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}"')
            conn.execute(f'SET search_path TO "{self._schema}"')
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    question_id TEXT NOT NULL,
                    version     INTEGER NOT NULL,
                    created_at  TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    k           INTEGER,
                    estimate    DOUBLE PRECISION,
                    ci_low      DOUBLE PRECISION,
                    ci_high     DOUBLE PRECISION,
                    measure     TEXT,
                    PRIMARY KEY (question_id, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    question_id   TEXT NOT NULL,
                    study_id      TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    PRIMARY KEY (question_id, study_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rob_decisions (
                    question_id   TEXT NOT NULL,
                    study_id      TEXT NOT NULL,
                    domain_key    TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    PRIMARY KEY (question_id, study_id, domain_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS development_events (
                    landscape_id TEXT NOT NULL,
                    asset_name   TEXT NOT NULL,
                    indication   TEXT NOT NULL,
                    source_type  TEXT NOT NULL,
                    event_type   TEXT NOT NULL,
                    event_date   TEXT NOT NULL,
                    event_json   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    PRIMARY KEY (landscape_id, asset_name, indication, source_type,
                                 event_type, event_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS landscape_links (
                    landscape_id TEXT NOT NULL,
                    asset_name   TEXT NOT NULL,
                    indication   TEXT NOT NULL,
                    question_id  TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    PRIMARY KEY (landscape_id, asset_name, indication)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subpop_cache (
                    nct_id      TEXT PRIMARY KEY,
                    subpop_json TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    application_number TEXT PRIMARY KEY,
                    drug          TEXT NOT NULL,
                    approval_json TEXT NOT NULL,
                    updated_at    TEXT NOT NULL
                )
                """
            )

    def drop_schema(self) -> None:
        """Tear down an isolated test schema; a no-op safety guard on `public`."""
        if self._schema == "public":
            return
        with self._connect() as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{self._schema}" CASCADE')

    # --- snapshots -----------------------------------------------------------

    def save_snapshot(self, result: ReviewResult) -> int:
        question_id = result.question.id
        pool = result.pool
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS m FROM snapshots WHERE question_id = %s",
                (question_id,),
            ).fetchone()
            version = row["m"] + 1
            conn.execute(
                """
                INSERT INTO snapshots
                    (question_id, version, created_at, result_json,
                     k, estimate, ci_low, ci_high, measure)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    question_id,
                    version,
                    _now(),
                    result.model_dump_json(),
                    pool.k if pool else 0,
                    pool.estimate if pool else None,
                    pool.ci_low if pool else None,
                    pool.ci_high if pool else None,
                    result.question.measure.value,
                ),
            )
        return version

    def load_latest(self, question_id: str) -> ReviewResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM snapshots WHERE question_id = %s "
                "ORDER BY version DESC LIMIT 1",
                (question_id,),
            ).fetchone()
        return ReviewResult.model_validate_json(row["result_json"]) if row else None

    def load_version(self, question_id: str, version: int) -> ReviewResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM snapshots WHERE question_id = %s AND version = %s",
                (question_id, version),
            ).fetchone()
        return ReviewResult.model_validate_json(row["result_json"]) if row else None

    def list_versions(self, question_id: str) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version FROM snapshots WHERE question_id = %s ORDER BY version",
                (question_id,),
            ).fetchall()
        return [r["version"] for r in rows]

    def list_snapshots(self, question_id: str) -> list[SnapshotMeta]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT question_id, version, created_at, k, estimate, ci_low, ci_high, measure "
                "FROM snapshots WHERE question_id = %s ORDER BY version",
                (question_id,),
            ).fetchall()
        return [
            SnapshotMeta(
                question_id=r["question_id"],
                version=r["version"],
                created_at=r["created_at"],
                k=r["k"] or 0,
                estimate=r["estimate"],
                ci_low=r["ci_low"],
                ci_high=r["ci_high"],
                measure=r["measure"] or "HR",
            )
            for r in rows
        ]

    def list_questions(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT question_id FROM snapshots ORDER BY question_id"
            ).fetchall()
        return [r["question_id"] for r in rows]

    # --- human decisions -----------------------------------------------------

    def save_decision(self, question_id: str, decision: ReviewDecision) -> None:
        if decision.timestamp is None:
            decision = decision.model_copy(update={"timestamp": _now()})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO decisions (question_id, study_id, decision_json, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(question_id, study_id)
                DO UPDATE SET decision_json = excluded.decision_json,
                              updated_at = excluded.updated_at
                """,
                (question_id, decision.study_id, decision.model_dump_json(), _now()),
            )

    def load_decisions(self, question_id: str) -> list[ReviewDecision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT decision_json FROM decisions WHERE question_id = %s ORDER BY study_id",
                (question_id,),
            ).fetchall()
        return [ReviewDecision.model_validate_json(r["decision_json"]) for r in rows]

    def save_rob_decision(self, question_id: str, decision: RobDecision) -> None:
        if decision.timestamp is None:
            decision = decision.model_copy(update={"timestamp": _now()})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rob_decisions
                    (question_id, study_id, domain_key, decision_json, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(question_id, study_id, domain_key)
                DO UPDATE SET decision_json = excluded.decision_json,
                              updated_at = excluded.updated_at
                """,
                (
                    question_id,
                    decision.study_id,
                    decision.domain_key,
                    decision.model_dump_json(),
                    _now(),
                ),
            )

    def load_rob_decisions(self, question_id: str) -> list[RobDecision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT decision_json FROM rob_decisions WHERE question_id = %s "
                "ORDER BY study_id, domain_key",
                (question_id,),
            ).fetchall()
        return [RobDecision.model_validate_json(r["decision_json"]) for r in rows]

    # --- competitive-intelligence: events + evidence links -------------------

    def save_events(self, landscape_id: str, events: list[DevelopmentEvent]) -> None:
        with self._connect() as conn:
            for e in events:
                conn.execute(
                    """
                    INSERT INTO development_events
                        (landscape_id, asset_name, indication, source_type,
                         event_type, event_date, event_json, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(landscape_id, asset_name, indication, source_type,
                                event_type, event_date)
                    DO UPDATE SET event_json = excluded.event_json,
                                  updated_at = excluded.updated_at
                    """,
                    (
                        landscape_id,
                        e.asset_name,
                        e.indication,
                        e.source_type.value,
                        e.event_type.value,
                        e.date or "",
                        e.model_dump_json(),
                        _now(),
                    ),
                )

    def load_events(self, landscape_id: str) -> list[DevelopmentEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_json FROM development_events WHERE landscape_id = %s "
                "ORDER BY event_date",
                (landscape_id,),
            ).fetchall()
        return [DevelopmentEvent.model_validate_json(r["event_json"]) for r in rows]

    def clear_events(self, landscape_id: str) -> None:
        """Drop a landscape's cached CT.gov events so it re-seeds from a fresh search.

        Mirrors SnapshotStore.clear_events — `save_events` only upserts, so a
        stale cache is cleaned by deleting it and re-pulling. Scoped to
        CT.gov-sourced events so ingested announcements/filings survive.
        """
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM development_events WHERE landscape_id = %s AND source_type = %s",
                (landscape_id, "ctgov"),
            )

    def save_link(
        self, landscape_id: str, asset_name: str, indication: str, question_id: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO landscape_links
                    (landscape_id, asset_name, indication, question_id, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(landscape_id, asset_name, indication)
                DO UPDATE SET question_id = excluded.question_id,
                              updated_at = excluded.updated_at
                """,
                (landscape_id, asset_name, indication, question_id, _now()),
            )

    def load_links(self, landscape_id: str) -> dict[tuple[str, str], str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT asset_name, indication, question_id FROM landscape_links "
                "WHERE landscape_id = %s",
                (landscape_id,),
            ).fetchall()
        return {(r["asset_name"], r["indication"]): r["question_id"] for r in rows}

    def load_all_links(self) -> dict[tuple[str, str], str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT asset_name, indication, question_id FROM landscape_links"
            ).fetchall()
        return {(r["asset_name"], r["indication"]): r["question_id"] for r in rows}

    # --- v2: sub-population cache + openFDA approvals cache -------------------

    def save_subpop(self, nct_id: str, subpop: SubPopulation) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO subpop_cache (nct_id, subpop_json, updated_at) VALUES (%s, %s, %s) "
                "ON CONFLICT(nct_id) DO UPDATE SET subpop_json = excluded.subpop_json, "
                "updated_at = excluded.updated_at",
                (nct_id, subpop.model_dump_json(), _now()),
            )

    def load_subpops(self, nct_ids: list[str]) -> dict[str, SubPopulation]:
        if not nct_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT nct_id, subpop_json FROM subpop_cache WHERE nct_id = ANY(%s)",
                (list(nct_ids),),
            ).fetchall()
        return {r["nct_id"]: SubPopulation.model_validate_json(r["subpop_json"]) for r in rows}

    def save_approvals(self, approvals: list[RegulatoryApproval]) -> None:
        with self._connect() as conn:
            for a in approvals:
                conn.execute(
                    "INSERT INTO approvals (application_number, drug, approval_json, updated_at) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT(application_number) DO UPDATE SET "
                    "approval_json = excluded.approval_json, updated_at = excluded.updated_at",
                    (a.application_number, a.drug, a.model_dump_json(), _now()),
                )

    def load_approvals(self, drug: str) -> list[RegulatoryApproval]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT approval_json FROM approvals WHERE drug = %s ORDER BY application_number",
                (drug,),
            ).fetchall()
        return [RegulatoryApproval.model_validate_json(r["approval_json"]) for r in rows]
