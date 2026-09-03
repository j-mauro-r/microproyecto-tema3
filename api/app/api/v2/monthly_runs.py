"""HU002 monthly-upload HTTP boundary; downstream HU003 work is intentionally absent."""

from http import HTTPStatus

from fastapi import APIRouter, File, Form, Request, UploadFile

from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import MonthlyUploadValidator
from api.app.schemas.errors import ErrorCode

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
) -> None:
    validator: MonthlyUploadValidator = request.app.state.monthly_upload_validator
    content = await _read_bounded(file, validator.max_bytes)
    result = validator.validate(
        filename=file.filename or "",
        content=content,
        reference_month=reference_month,
        content_type=file.content_type,
    )
    # A 201 represents the full pipeline contract and belongs to HU003+.
    raise ContractError(
        ErrorCode.CHAMPION_NOT_READY,
        "La carga es válida, pero el procesamiento Champion aún no está disponible.",
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        details={
            "reason": "downstream_pipeline_not_available",
            "source_file": {
                "original_name": result.metadata.original_name,
                "size_bytes": result.metadata.size_bytes,
                "sha256": result.metadata.sha256,
            },
            "reference_month": result.reference_month,
        },
    )
