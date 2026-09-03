"""Uniform FastAPI error handling with sanitized public responses."""

from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.app.schemas.errors import ErrorCode, ErrorDetail, ErrorEnvelope
from api.app.domain.errors import ContractError


def _request_id(request: Request) -> UUID:
    return getattr(request.state, "request_id", uuid4())


def _response(status_code: int, detail: ErrorDetail) -> JSONResponse:
    envelope = ErrorEnvelope(error=detail)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {
        "errors": [
            {"location": list(error["loc"]), "type": error["type"], "message": error["msg"]}
            for error in exc.errors()
        ]
    }
    return _response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        ErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            message="La solicitud no cumple el contrato esperado.",
            request_id=_request_id(request),
            details=details,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "La solicitud no pudo ser procesada."
    code = ErrorCode.INVALID_REQUEST if exc.status_code < 500 else ErrorCode.INTERNAL_ERROR
    return _response(
        exc.status_code,
        ErrorDetail(code=code, message=message, request_id=_request_id(request)),
    )


async def unexpected_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    return _response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="Ocurrió un error interno inesperado.",
            request_id=_request_id(request),
        ),
    )


async def contract_error_handler(request: Request, exc: ContractError) -> JSONResponse:
    return _response(
        exc.status_code,
        ErrorDetail(
            code=exc.code,
            message=exc.message,
            request_id=_request_id(request),
            stage=exc.stage,
            details=exc.details,
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ContractError, contract_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
