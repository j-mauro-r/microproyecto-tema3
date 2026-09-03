"""HU002 monthly-upload HTTP boundary; downstream HU003 work is intentionally absent."""

from http import HTTPStatus

from fastapi import APIRouter, File, Form, Request, UploadFile

from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadValidator
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator, MonthlyRunCommand, MonthlyRunResult
from api.app.persistence.service import MonthlyRunPersistenceService
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus

router = APIRouter(tags=["monthly-runs"])
_READ_CHUNK_BYTES = 64 * 1024


async def _read_bounded(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    received = 0
    while chunk := await upload.read(_READ_CHUNK_BYTES):
        received += len(chunk)
        if received > max_bytes:
            raise ContractError(
                ErrorCode.INVALID_UPLOAD,
                "El archivo supera el límite configurado.",
                details={"reason": "file_too_large", "max_bytes": max_bytes},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/monthly-runs", status_code=HTTPStatus.CREATED)
async def create_monthly_run(
    request: Request,
    file: UploadFile = File(...),
    reference_month: str = Form(...),
) -> dict[str, object]:
    validator: MonthlyUploadValidator = request.app.state.monthly_upload_validator
    content = await _read_bounded(file, validator.max_bytes)
    orchestrator: MonthlyPredictionOrchestrator | None = request.app.state.monthly_orchestrator
    persistence: MonthlyRunPersistenceService | None = request.app.state.monthly_run_persistence
    if orchestrator is None or persistence is None:
        validated = validator.validate(
            filename=file.filename or "", content=content, reference_month=reference_month,
            content_type=file.content_type,
        )
        raise ContractError(
            ErrorCode.PERSISTENCE_FAILED,
            "La carga es válida, pero la persistencia durable aún no está disponible.",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            stage=RunStatus.PERSISTING,
            details={"reason": "durable_persistence_not_available", "source_file": {
                "original_name": validated.metadata.original_name,
                "size_bytes": validated.metadata.size_bytes,
                "sha256": validated.metadata.sha256,
            }, "reference_month": validated.reference_month},
        )

    result = orchestrator.run(MonthlyRunCommand(
        reference_month=reference_month,
        source_file_name=file.filename or "",
        source_bytes=content,
        request_id=str(request.state.request_id),
        content_type=file.content_type,
    ))
    if result.status is RunStatus.FAILED:
        persistence.persist(result)
        raise _run_failure(result)
    completed = persistence.persist(result)
    snapshot = completed.snapshot
    if completed.status is not RunStatus.COMPLETED or snapshot is None:
        raise ContractError(
            ErrorCode.PERSISTENCE_FAILED,
            "No fue posible confirmar la persistencia durable del run mensual.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            stage=RunStatus.PERSISTING,
        )
    return {
        "schema_version": "2.0.0",
        "request_id": completed.request_id,
        "run": {
            "run_id": completed.run_id, "status": completed.status.value,
            "reference_month": completed.reference_month, "created_at": completed.created_at,
            "completed_at": completed.completed_at,
            "source_file_sha256": completed.source_file_sha256,
            "champion_version": completed.champion_version,
        },
        "prediction_snapshot": {
            "run_id": snapshot.run_id, "generated_at": snapshot.generated_at,
            "reference_month": snapshot.reference_month,
            "source_file_sha256": snapshot.source_file_sha256,
            "champion": {
                "name": snapshot.champion.name, "version": snapshot.champion.version,
                "output_type": snapshot.champion.output_type,
                "supported_horizons": list(snapshot.champion.supported_horizons),
                "feature_contract_version": snapshot.champion.feature_contract_version,
                "feature_contract_sha256": snapshot.champion.feature_contract_sha256,
            },
            "predictions": [
                {field: getattr(item, field) for field in (
                    "divipola", "municipality", "horizon", "target_month", "output_type",
                    "probability", "expected_cases", "risk_score", "label",
                    "decision_threshold",
                )}
                for item in snapshot.predictions
            ],
        },
    }


def _run_failure(result: MonthlyRunResult) -> ContractError:
    code = result.error_code or ErrorCode.INTERNAL_ERROR
    status_code = (
        HTTPStatus.SERVICE_UNAVAILABLE if code is ErrorCode.CHAMPION_NOT_READY
        else HTTPStatus.UNPROCESSABLE_ENTITY if code is ErrorCode.INVALID_UPLOAD
        else HTTPStatus.INTERNAL_SERVER_ERROR
    )
    return ContractError(
        code, result.error_message or "El run mensual no pudo completarse.",
        status_code=status_code, stage=result.error_stage or RunStatus.FAILED,
    )
