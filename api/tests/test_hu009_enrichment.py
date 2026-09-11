from dataclasses import replace
from datetime import datetime, timezone
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

from api.app.core.config import Settings
from api.app.domain.enrichment import (
    CurrentStatusSnapshot, DataQualitySnapshot, DecisionRuleSnapshot,
    LocalExplanation, MaterializedShapExplanationProvider,
    UnavailableExplanationProvider, build_current_status, build_quality, ratio_to_p75,
)
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.persistence.sqlite import SQLiteUnitOfWork
from api.tests.test_monthly_orchestrator import metadata
from api.tests.test_monthly_upload_validator import csv_bytes
from api.tests.test_persistence import NOW, _ready


def _upload():
    return MonthlyUploadValidator(max_bytes=100_000, contract=MonthlyUploadContract()).validate(
        filename="monthly.csv", content=csv_bytes(), reference_month="2026-01"
    )


def test_quality_uses_validated_cut_without_inventing_completeness():
    quality = build_quality(_upload())
    assert quality.status == "complete" and quality.last_observed_month == "2026-01"
    assert quality.epidemiological_completeness is None
    assert quality.climate_completeness is None and quality.warnings


def test_current_status_is_partial_and_never_uses_lag_as_observed_cases():
    statuses = build_current_status(_upload())
    assert set(statuses) == {"68001", "76001"}
    assert all(item.observed_cases is None and item.p50 is None for item in statuses.values())
    assert all(item.p25 is not None and item.p75 is not None for item in statuses.values())


def test_ratio_requires_observed_cases_and_positive_p75():
    assert ratio_to_p75(12, 6) == 2
    assert ratio_to_p75(None, 6) is None
    assert ratio_to_p75(12, 0) is None and ratio_to_p75(12, None) is None


def test_unavailable_provider_is_explicit_and_empty():
    result = UnavailableExplanationProvider().get_explanation(
        reference_month="2026-01", divipola="68001", horizon="T+1",
        champion_metadata=metadata(),
    )
    assert result == LocalExplanation(available=False)


def test_materialized_shap_requires_exact_month_city_horizon_and_preserves_sign(tmp_path):
    t1 = tmp_path / "t1.parquet"
    t2 = tmp_path / "t2.parquet"
    pq.write_table(pa.Table.from_pylist([
        {"divipola": "68001", "anio": 2026, "mes": 1,
         "shap_rain": -0.8, "shap_temp": 0.3, "rain": 5.0, "temp": 28.0},
        {"divipola": "76001", "anio": 2026, "mes": 1,
         "shap_rain": 0.2, "shap_temp": -0.1, "rain": 2.0, "temp": 30.0},
    ]), t1)
    pq.write_table(pa.Table.from_pylist([
        {"divipola": "68001", "anio": 2026, "mes": 1,
         "shap_rain": 0.1, "shap_temp": 0.9, "rain": 5.0, "temp": 28.0},
    ]), t2)
    provider = MaterializedShapExplanationProvider(
        {"T+1": str(t1), "T+2": str(t2)},
        feature_contract_version="contract-v1", feature_contract_sha256="contract-sha",
    )
    explanation = provider.get_explanation(reference_month="2026-01", divipola="68001",
        horizon="T+1", champion_metadata=metadata())
    assert explanation.available and explanation.method == "shap" and explanation.scope == "local"
    assert [(item.feature, item.contribution) for item in explanation.top_features] == [
        ("rain", -0.8), ("temp", 0.3)]
    assert not provider.get_explanation(reference_month="2026-02", divipola="68001",
        horizon="T+1", champion_metadata=metadata()).available
    assert not provider.get_explanation(reference_month="2026-01", divipola="76001",
        horizon="T+2", champion_metadata=metadata()).available


def test_corrupt_or_missing_shap_is_unavailable(tmp_path):
    corrupt = tmp_path / "bad.parquet"
    corrupt.write_text("not parquet")
    provider = MaterializedShapExplanationProvider(
        {"T+1": str(corrupt)}, feature_contract_version="contract-v1",
        feature_contract_sha256="contract-sha",
    )
    assert not provider.get_explanation(reference_month="2026-01", divipola="68001",
        horizon="T+1", champion_metadata=metadata()).available
    assert not provider.get_explanation(reference_month="2026-01", divipola="68001",
        horizon="T+2", champion_metadata=metadata()).available


def _enriched_ready():
    ready = _ready()
    quality = DataQualitySnapshot("complete", "2026-01", warnings=("warning real",))
    statuses = (("68001", CurrentStatusSnapshot("2026-01", p25=2, p75=8)),)
    predictions = tuple(replace(item,
        decision_rule=DecisionRuleSnapshot("probability_threshold", item.decision_threshold),
        explanation=LocalExplanation(False)) for item in ready.snapshot.predictions)
    champion = replace(ready.snapshot.champion, decision_rule_version="rule-v1")
    return replace(ready, snapshot=replace(ready.snapshot, champion=champion,
        predictions=predictions, data_quality=quality, current_status=statuses))


def test_persistence_api_and_history_round_trip_enrichments(tmp_path):
    path = tmp_path / "hu009.sqlite"
    service = MonthlyRunPersistenceService(lambda: SQLiteUnitOfWork(str(path)), clock=lambda: NOW)
    completed = service.persist(_enriched_ready())
    recovered = service.get(completed.run_id).snapshot
    assert recovered.data_quality.warnings == ("warning real",)
    assert recovered.predictions[0].decision_rule.probability_threshold == 0.61
    settings = Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                        debug=False, cors_origins=(), db_path=str(path))
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        latest = client.get("/api/v2/predictions/latest").json()["prediction_snapshot"]
        history = client.get("/api/v2/predictions/history").json()["items"][0]
    assert latest["data_quality"]["warnings"] == ["warning real"]
    assert latest["current_status"]["68001"]["observed_cases"] is None
    assert latest["predictions"][0]["explanation"]["available"] is False
    assert history["run_id"] == latest["run_id"] and history["data_quality"] == latest["data_quality"]


def test_legacy_snapshot_without_enrichment_remains_readable(tmp_path):
    path = tmp_path / "legacy.sqlite"
    service = MonthlyRunPersistenceService(lambda: SQLiteUnitOfWork(str(path)), clock=lambda: NOW)
    completed = service.persist(_ready())
    snapshot = service.get(completed.run_id).snapshot
    assert snapshot.data_quality is None and snapshot.current_status == ()
    assert all(not item.explanation.available for item in snapshot.predictions)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        for table in ("prediction_enrichments", "current_status", "snapshot_quality", "champion_enrichments"):
            connection.execute(f"DROP TABLE {table}")
    settings = Settings(service_name="biomac-api", api_version="2.0.0", environment="test",
                        debug=False, cors_origins=(), db_path=str(path))
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/api/v2/predictions/latest")
    body = response.json()["prediction_snapshot"]
    assert response.status_code == 200 and body["data_quality"] is None
    assert body["predictions"][0]["explanation"]["available"] is False
