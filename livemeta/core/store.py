"""Snapshot store: versioned ReviewResult persistence keyed by question id.

A single-file SQLite database (Slice 5). The public interface — save_snapshot /
load_latest / list_versions plus the decision round-trips — is unchanged from the
Slice-2 JSON store it replaces, so every caller and its tests are untouched. The
version list is the audit-trail history the living layer reads; load_version and
list_snapshots expose past runs and their timestamps.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .schema import ReviewDecision, ReviewResult, RobDecision, SnapshotMeta

_DEFAULT_DIR = ".livemeta_data"
_DB_NAME = "livemeta.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SnapshotStore:
    def __init__(self, data_dir: str | Path | None = None):
        base = data_dir or os.environ.get("LIVEMETA_DATA_DIR", _DEFAULT_DIR)
        self._dir = Path(base)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db = self._dir / _DB_NAME
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        # A fresh connection per call: save_snapshot runs inside anyio.to_thread on
        # the WebSocket path, so sharing one connection across threads would raise.
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    question_id TEXT NOT NULL,
                    version     INTEGER NOT NULL,
                    created_at  TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    k           INTEGER,
                    estimate    REAL,
                    ci_low      REAL,
                    ci_high     REAL,
                    measure     TEXT,
                    PRIMARY KEY (question_id, version)
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    question_id   TEXT NOT NULL,
                    study_id      TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    PRIMARY KEY (question_id, study_id)
                );
                CREATE TABLE IF NOT EXISTS rob_decisions (
                    question_id   TEXT NOT NULL,
                    study_id      TEXT NOT NULL,
                    domain_key    TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    PRIMARY KEY (question_id, study_id, domain_key)
                );
                """
            )
            conn.commit()

    # --- snapshots -----------------------------------------------------------

    def save_snapshot(self, result: ReviewResult) -> int:
        """Append a snapshot for its question; return the new version number."""
        question_id = result.question.id
        pool = result.pool
        with closing(self._connect()) as conn, conn:
            (max_version,) = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM snapshots WHERE question_id = ?",
                (question_id,),
            ).fetchone()
            version = max_version + 1
            conn.execute(
                """
                INSERT INTO snapshots
                    (question_id, version, created_at, result_json,
                     k, estimate, ci_low, ci_high, measure)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT result_json FROM snapshots WHERE question_id = ? "
                "ORDER BY version DESC LIMIT 1",
                (question_id,),
            ).fetchone()
        return ReviewResult.model_validate_json(row["result_json"]) if row else None

    def load_version(self, question_id: str, version: int) -> ReviewResult | None:
        """Load one specific historical version (for the read-only audit view)."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT result_json FROM snapshots WHERE question_id = ? AND version = ?",
                (question_id, version),
            ).fetchone()
        return ReviewResult.model_validate_json(row["result_json"]) if row else None

    def list_versions(self, question_id: str) -> list[int]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT version FROM snapshots WHERE question_id = ? ORDER BY version",
                (question_id,),
            ).fetchall()
        return [r["version"] for r in rows]

    def list_snapshots(self, question_id: str) -> list[SnapshotMeta]:
        """The version timeline with headline numbers — the audit-trail history."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT question_id, version, created_at, k, estimate, ci_low, ci_high, measure "
                "FROM snapshots WHERE question_id = ? ORDER BY version",
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
        """All question ids with at least one saved snapshot — feeds the dashboard."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT DISTINCT question_id FROM snapshots ORDER BY question_id"
            ).fetchall()
        return [r["question_id"] for r in rows]

    # --- human decisions -----------------------------------------------------

    def save_decision(self, question_id: str, decision: ReviewDecision) -> None:
        """Record a human confirm/flag; the latest decision per trial wins."""
        if decision.timestamp is None:
            decision = decision.model_copy(update={"timestamp": _now()})
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO decisions (question_id, study_id, decision_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(question_id, study_id)
                DO UPDATE SET decision_json = excluded.decision_json,
                              updated_at = excluded.updated_at
                """,
                (question_id, decision.study_id, decision.model_dump_json(), _now()),
            )

    def load_decisions(self, question_id: str) -> list[ReviewDecision]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT decision_json FROM decisions WHERE question_id = ? ORDER BY study_id",
                (question_id,),
            ).fetchall()
        return [ReviewDecision.model_validate_json(r["decision_json"]) for r in rows]

    def save_rob_decision(self, question_id: str, decision: RobDecision) -> None:
        """Record a human RoB 2 domain sign-off; latest per (study, domain) wins."""
        if decision.timestamp is None:
            decision = decision.model_copy(update={"timestamp": _now()})
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO rob_decisions
                    (question_id, study_id, domain_key, decision_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
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
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT decision_json FROM rob_decisions WHERE question_id = ? "
                "ORDER BY study_id, domain_key",
                (question_id,),
            ).fetchall()
        return [RobDecision.model_validate_json(r["decision_json"]) for r in rows]
