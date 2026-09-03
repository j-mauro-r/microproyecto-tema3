"""SQLite repositories and unit of work. SQL is confined to this module."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from api.app.champion.models import ChampionMetadata
from api.app.orchestration.monthly import (
    CandidatePrediction,
    MonthlyRunResult,
    PredictionSnapshotCandidate,
)
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    request_id TEXT NULL,
    status TEXT NOT NULL,
    stages_json TEXT NOT NULL,
    reference_month TEXT NOT NULL,
    source_file_sha256 TEXT NULL,
    idempotency_key TEXT NULL UNIQUE,
    champion_name TEXT NULL,
    champion_version TEXT NULL,
    feature_contract_version TEXT NULL,
    feature_contract_sha256 TEXT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    completed_at TEXT NULL,
    error_code TEXT NULL,
    error_stage TEXT NULL,
    error_message TEXT NULL,
    created_db_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id TEXT NOT NULL,
    divipola TEXT NOT NULL,
    municipality TEXT NOT NULL,
    horizon TEXT NOT NULL,
    target_month TEXT NOT NULL,
    output_type TEXT NOT NULL,
    probability REAL NULL,
    expected_cases REAL NULL,
    risk_score REAL NULL,
    label TEXT NULL,
    decision_threshold REAL NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, divipola, horizon)
);
"""


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


class SQLiteUnitOfWork:
    def __init__(self, db_path: str) -> None:
        if not db_path.strip():
            raise ValueError("db_path must not be empty")
        self.db_path = db_path
        self.connection: sqlite3.Connection | None = None
        self.runs: SQLiteRunRepository
        self.predictions: SQLitePredictionRepository
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        path = Path(self.db_path)
        if self.db_path != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.executescript(_SCHEMA)
        finally:
            connection.close()

    def foreign_keys_enabled(self) -> bool:
        connection = self._connect()
        try:
            return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            connection.close()

    def __enter__(self) -> SQLiteUnitOfWork:
        self.connection = self._connect()
        self.connection.execute("BEGIN IMMEDIATE")
        self.runs = SQLiteRunRepository(self.connection)
        self.predictions = SQLitePredictionRepository(self.connection)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self.connection is not None
        try:
            self.connection.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self.connection.close()
            self.connection = None


class SQLiteRunRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save(self, result: MonthlyRunResult) -> None:
        champion = result.snapshot.champion if result.snapshot else None
        self._connection.execute(
            """INSERT INTO runs (
                run_id, request_id, status, stages_json, reference_month,
                source_file_sha256, idempotency_key, champion_name, champion_version,
                feature_contract_version, feature_contract_sha256, created_at, finished_at,
                completed_at, error_code, error_stage, error_message, created_db_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.run_id,
                result.request_id,
                result.status.value,
                json.dumps([stage.value for stage in result.stages]),
                result.reference_month,
                result.source_file_sha256,
                result.idempotency_key,
                champion.name if champion else None,
                result.champion_version,
                champion.feature_contract_version if champion else None,
                champion.feature_contract_sha256 if champion else None,
                _iso(result.created_at),
                _iso(result.finished_at),
                _iso(result.completed_at) if result.completed_at else None,
                result.error_code.value if result.error_code else None,
                result.error_stage.value if result.error_stage else None,
                result.error_message,
                _iso(datetime.now(timezone.utc)),
            ),
        )

    def mark_completed(self, run_id: str, completed_at: object) -> None:
        if not isinstance(completed_at, datetime):
            raise TypeError("completed_at must be datetime")
        row = self._connection.execute(
            "SELECT stages_json FROM runs WHERE run_id = ? AND status = ?",
            (run_id, RunStatus.PERSISTING.value),
        ).fetchone()
        if row is None:
            raise RuntimeError("run transition to completed failed")
        stages = json.loads(row["stages_json"])
        stages.append(RunStatus.COMPLETED.value)
        cursor = self._connection.execute(
            """UPDATE runs
               SET status = ?, completed_at = ?, finished_at = ?,
                   stages_json = ?
               WHERE run_id = ? AND status = ?""",
            (
                RunStatus.COMPLETED.value,
                _iso(completed_at),
                _iso(completed_at),
                json.dumps(stages),
                run_id,
                RunStatus.PERSISTING.value,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("run transition to completed failed")

    def get(self, run_id: str) -> MonthlyRunResult | None:
        row = self._connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _row_to_run(self._connection, row) if row else None

    def find_by_idempotency_key(self, key: str) -> MonthlyRunResult | None:
        row = self._connection.execute(
            "SELECT * FROM runs WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return _row_to_run(self._connection, row) if row else None


class SQLitePredictionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_snapshot(self, snapshot: PredictionSnapshotCandidate) -> None:
        self._connection.executemany(
            """INSERT INTO predictions (
                run_id, divipola, municipality, horizon, target_month, output_type,
                probability, expected_cases, risk_score, label, decision_threshold,
                generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    snapshot.run_id,
                    item.divipola,
                    item.municipality,
                    item.horizon,
                    item.target_month,
                    item.output_type,
                    item.probability,
                    item.expected_cases,
                    item.risk_score,
                    item.label,
                    item.decision_threshold,
                    _iso(snapshot.generated_at),
                )
                for item in snapshot.predictions
            ],
        )

    def get_by_run_id(self, run_id: str) -> PredictionSnapshotCandidate | None:
        run = self._connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _load_snapshot(self._connection, run) if run else None


def _row_to_run(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> MonthlyRunResult:
    snapshot = _load_snapshot(connection, row)
    return MonthlyRunResult(
        run_id=row["run_id"],
        request_id=row["request_id"],
        status=RunStatus(row["status"]),
        stages=tuple(RunStatus(item) for item in json.loads(row["stages_json"])),
        reference_month=row["reference_month"],
        source_file_sha256=row["source_file_sha256"],
        idempotency_key=row["idempotency_key"],
        champion_version=row["champion_version"],
        created_at=_datetime(row["created_at"]),
        finished_at=_datetime(row["finished_at"]),
        snapshot=snapshot,
        error_code=ErrorCode(row["error_code"]) if row["error_code"] else None,
        error_stage=RunStatus(row["error_stage"]) if row["error_stage"] else None,
        error_message=row["error_message"],
        completed_at=_datetime(row["completed_at"]),
    )


def _load_snapshot(
    connection: sqlite3.Connection, run: sqlite3.Row
) -> PredictionSnapshotCandidate | None:
    rows = connection.execute(
        """SELECT * FROM predictions WHERE run_id = ?
           ORDER BY CASE divipola WHEN '68001' THEN 1 WHEN '76001' THEN 2 ELSE 3 END,
                    CASE horizon WHEN 'T+1' THEN 1 WHEN 'T+2' THEN 2 ELSE 3 END""",
        (run["run_id"],),
    ).fetchall()
    if not rows:
        return None
    horizons = tuple(dict.fromkeys(row["horizon"] for row in rows))
    champion = ChampionMetadata(
        name=run["champion_name"],
        version=run["champion_version"],
        supported_horizons=horizons,
        output_type=rows[0]["output_type"],
        feature_contract_version=run["feature_contract_version"],
        feature_contract_sha256=run["feature_contract_sha256"],
    )
    return PredictionSnapshotCandidate(
        run_id=run["run_id"],
        generated_at=_datetime(rows[0]["generated_at"]),
        reference_month=run["reference_month"],
        source_file_sha256=run["source_file_sha256"],
        champion=champion,
        predictions=tuple(
            CandidatePrediction(
                divipola=row["divipola"],
                municipality=row["municipality"],
                horizon=row["horizon"],
                target_month=row["target_month"],
                output_type=row["output_type"],
                probability=row["probability"],
                expected_cases=row["expected_cases"],
                risk_score=row["risk_score"],
                label=row["label"],
                decision_threshold=row["decision_threshold"],
            )
            for row in rows
        ),
    )
