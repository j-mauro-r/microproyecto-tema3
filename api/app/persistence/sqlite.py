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
from api.app.query.service import HistoryFilters

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

CREATE TABLE IF NOT EXISTS snapshot_quality (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_observed_month TEXT NOT NULL,
    epidemiological_completeness REAL NULL,
    climate_completeness REAL NULL,
    warnings_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS current_status (
    run_id TEXT NOT NULL,
    divipola TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, divipola)
);

CREATE TABLE IF NOT EXISTS prediction_enrichments (
    run_id TEXT NOT NULL,
    divipola TEXT NOT NULL,
    horizon TEXT NOT NULL,
    decision_rule_json TEXT NULL,
    explanation_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, divipola, horizon)
);

CREATE TABLE IF NOT EXISTS champion_enrichments (
    run_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
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
        quality = snapshot.data_quality
        if quality is not None:
            self._connection.execute(
                "INSERT INTO snapshot_quality VALUES (?, ?, ?, ?, ?, ?)",
                (snapshot.run_id, quality.status, quality.last_observed_month,
                 quality.epidemiological_completeness, quality.climate_completeness,
                 json.dumps(quality.warnings)),
            )
        self._connection.executemany(
            "INSERT INTO current_status VALUES (?, ?, ?)",
            [(snapshot.run_id, code, json.dumps({
                "reference_month": status.reference_month,
                "observed_cases": status.observed_cases, "p25": status.p25,
                "p50": status.p50, "p75": status.p75,
                "ratio_to_p75": status.ratio_to_p75, "endemic_zone": status.endemic_zone,
            })) for code, status in snapshot.current_status],
        )
        self._connection.executemany(
            "INSERT INTO prediction_enrichments VALUES (?, ?, ?, ?, ?)",
            [(snapshot.run_id, item.divipola, item.horizon,
              json.dumps({"type": item.decision_rule.type,
                          "probability_threshold": item.decision_rule.probability_threshold,
                          "target_month_p75": item.decision_rule.target_month_p75,
                          "decision_threshold_cases": item.decision_rule.decision_threshold_cases,
                          "version": item.decision_rule.version}) if item.decision_rule else None,
              json.dumps({"available": item.explanation.available,
                          "method": item.explanation.method, "scope": item.explanation.scope,
                          "top_features": [{"feature": feature.feature, "value": feature.value,
                                            "contribution": feature.contribution,
                                            "group": feature.group}
                                           for feature in item.explanation.top_features]}))
             for item in snapshot.predictions],
        )
        champion = snapshot.champion
        self._connection.execute(
            "INSERT INTO champion_enrichments VALUES (?, ?)",
            (snapshot.run_id, json.dumps({"mlflow_run_id": champion.mlflow_run_id,
             "artifact_sha256": champion.artifact_sha256,
             "decision_rule_version": champion.decision_rule_version,
             "explanation_method": champion.explanation_method})),
        )

    def get_by_run_id(self, run_id: str) -> PredictionSnapshotCandidate | None:
        run = self._connection.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _load_snapshot(self._connection, run) if run else None


class SQLitePredictionQueryRepository:
    """Open a query-only connection for each operation; never starts a write transaction."""

    def __init__(self, db_path: str) -> None:
        if not db_path.strip():
            raise ValueError("db_path must not be empty")
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        uri = f"{Path(self._db_path).resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def get_run(self, run_id: str) -> MonthlyRunResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return _row_to_run(connection, row) if row else None

    def get_latest_completed(
        self, municipality_codes: tuple[str, ...], horizons: tuple[str, ...]
    ) -> MonthlyRunResult | None:
        predicate, parameters = _prediction_filter(municipality_codes, horizons)
        with self._connect() as connection:
            row = connection.execute(
                f"""SELECT runs.* FROM runs
                    WHERE runs.status = ? AND runs.completed_at IS NOT NULL
                      AND EXISTS (
                          SELECT 1 FROM predictions
                          WHERE predictions.run_id = runs.run_id AND {predicate}
                      )
                    ORDER BY runs.completed_at DESC, runs.run_id DESC
                    LIMIT 1""",
                (RunStatus.COMPLETED.value, *parameters),
            ).fetchone()
            return _row_to_run(connection, row) if row else None

    def list_completed(self, filters: HistoryFilters) -> tuple[MonthlyRunResult, ...]:
        horizons = (filters.horizon,) if filters.horizon else ("T+1", "T+2")
        predicate, prediction_parameters = _prediction_filter(
            filters.municipality_codes, horizons
        )
        conditions = [
            "runs.status = ?", "runs.completed_at IS NOT NULL",
            f"EXISTS (SELECT 1 FROM predictions WHERE predictions.run_id = runs.run_id AND {predicate})",
        ]
        parameters: list[object] = [RunStatus.COMPLETED.value, *prediction_parameters]
        if filters.from_month is not None:
            conditions.append("runs.reference_month >= ?")
            parameters.append(filters.from_month)
        if filters.to_month is not None:
            conditions.append("runs.reference_month <= ?")
            parameters.append(filters.to_month)
        parameters.extend((filters.limit, filters.offset))
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT runs.* FROM runs
                    WHERE {' AND '.join(conditions)}
                    ORDER BY runs.reference_month DESC, runs.completed_at DESC, runs.run_id DESC
                    LIMIT ? OFFSET ?""",
                parameters,
            ).fetchall()
            return tuple(_row_to_run(connection, row) for row in rows)


def _prediction_filter(
    municipality_codes: tuple[str, ...], horizons: tuple[str, ...]
) -> tuple[str, tuple[str, ...]]:
    municipality_marks = ", ".join("?" for _ in municipality_codes)
    horizon_marks = ", ".join("?" for _ in horizons)
    return (
        f"predictions.divipola IN ({municipality_marks}) "
        f"AND predictions.horizon IN ({horizon_marks})",
        (*municipality_codes, *horizons),
    )


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
    champion_payload = _optional_json(connection, "champion_enrichments", run["run_id"])
    champion = ChampionMetadata(
        name=run["champion_name"],
        version=run["champion_version"],
        supported_horizons=horizons,
        output_type=rows[0]["output_type"],
        feature_contract_version=run["feature_contract_version"],
        feature_contract_sha256=run["feature_contract_sha256"],
        **champion_payload,
    )
    from api.app.domain.enrichment import (
        CurrentStatusSnapshot, DataQualitySnapshot, DecisionRuleSnapshot,
        ExplanationFeature, LocalExplanation,
    )
    quality_row = _optional_row(connection, "snapshot_quality", run["run_id"])
    quality = DataQualitySnapshot(
        status=quality_row["status"], last_observed_month=quality_row["last_observed_month"],
        epidemiological_completeness=quality_row["epidemiological_completeness"],
        climate_completeness=quality_row["climate_completeness"],
        warnings=tuple(json.loads(quality_row["warnings_json"])),
    ) if quality_row else None
    status_rows = _optional_rows(connection, "current_status", run["run_id"])
    statuses = tuple((row["divipola"], CurrentStatusSnapshot(**json.loads(row["payload_json"])))
                     for row in status_rows)
    enrichment_rows = {(row["divipola"], row["horizon"]): row for row in
                       _optional_rows(connection, "prediction_enrichments", run["run_id"])}
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
                decision_rule=_decision_rule(enrichment_rows.get((row["divipola"], row["horizon"]))),
                explanation=_explanation(enrichment_rows.get((row["divipola"], row["horizon"]))),
            )
            for row in rows
        ),
        data_quality=quality,
        current_status=statuses,
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _optional_row(connection: sqlite3.Connection, table: str, run_id: str):
    return connection.execute(f"SELECT * FROM {table} WHERE run_id = ?", (run_id,)).fetchone() if _table_exists(connection, table) else None


def _optional_rows(connection: sqlite3.Connection, table: str, run_id: str):
    return connection.execute(f"SELECT * FROM {table} WHERE run_id = ?", (run_id,)).fetchall() if _table_exists(connection, table) else []


def _optional_json(connection: sqlite3.Connection, table: str, run_id: str) -> dict:
    row = _optional_row(connection, table, run_id)
    return json.loads(row["payload_json"]) if row else {}


def _decision_rule(row):
    from api.app.domain.enrichment import DecisionRuleSnapshot
    return DecisionRuleSnapshot(**json.loads(row["decision_rule_json"])) if row and row["decision_rule_json"] else None


def _explanation(row):
    from api.app.domain.enrichment import ExplanationFeature, LocalExplanation
    if not row:
        return LocalExplanation(available=False)
    payload = json.loads(row["explanation_json"])
    payload["top_features"] = tuple(ExplanationFeature(**item) for item in payload["top_features"])
    return LocalExplanation(**payload)
