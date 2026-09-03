"""Pure, offline validation for a monthly source-file upload."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath

from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode

_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True, slots=True)
class MonthlyUploadContract:
    """Explicit structural rules; an empty format allowlist fails closed."""

    allowed_extensions: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    temporal_column: str | None = None
    municipality_column: str | None = None
    required_municipalities: tuple[str, ...] = ()
    supported_municipalities: tuple[str, ...] = ("68001", "76001")


@dataclass(frozen=True, slots=True)
class UploadMetadata:
    original_name: str
    size_bytes: int
    sha256: str
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedMonthlyUpload:
    reference_month: str
    metadata: UploadMetadata
    content: bytes
    columns: tuple[str, ...]


class MonthlyUploadValidator:
    def __init__(self, *, max_bytes: int, contract: MonthlyUploadContract) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        self._max_bytes = max_bytes
        self._contract = contract

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def validate(
        self,
        *,
        filename: str,
        content: bytes,
        reference_month: str,
        content_type: str | None = None,
    ) -> ValidatedMonthlyUpload:
        self._validate_reference_month(reference_month)
        if not content:
            self._invalid_upload("El archivo está vacío.", reason="empty_file")
        if len(content) > self._max_bytes:
            self._invalid_upload(
                "El archivo supera el límite configurado.",
                reason="file_too_large",
                max_bytes=self._max_bytes,
            )

        extension = PurePath(filename).suffix.lower()
        if not self._contract.allowed_extensions:
            self._invalid_upload(
                "No existe un formato mensual habilitado por contrato.",
                reason="format_contract_missing",
            )
        if extension not in self._contract.allowed_extensions:
            self._invalid_upload(
                "El formato del archivo no está permitido.",
                reason="unsupported_format",
                allowed_extensions=list(self._contract.allowed_extensions),
            )
        if extension != ".csv":
            self._invalid_upload(
                "El formato habilitado no tiene un parser implementado.",
                reason="parser_not_available",
            )

        columns, rows = self._parse_csv(content)
        missing = sorted(set(self._contract.required_columns) - set(columns))
        if missing:
            self._invalid_upload(
                "Faltan columnas requeridas.", reason="missing_columns", columns=missing
            )
        self._validate_rows(rows, reference_month)
        return ValidatedMonthlyUpload(
            reference_month=reference_month,
            metadata=UploadMetadata(
                original_name=PurePath(filename).name,
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                content_type=content_type,
            ),
            content=content,
            columns=columns,
        )

    @staticmethod
    def _validate_reference_month(value: str) -> None:
        match = _MONTH_PATTERN.fullmatch(value)
        if match is None:
            raise ContractError(
                ErrorCode.INVALID_REQUEST,
                "reference_month debe cumplir YYYY-MM.",
                details={"field": "reference_month"},
            )
        try:
            date(int(match.group(1)), int(match.group(2)), 1)
        except ValueError as exc:
            raise ContractError(
                ErrorCode.INVALID_REQUEST,
                "reference_month debe representar un mes válido.",
                details={"field": "reference_month"},
            ) from exc

    def _parse_csv(self, content: bytes) -> tuple[tuple[str, ...], list[dict[str, str]]]:
        try:
            text = content.decode("utf-8-sig", errors="strict")
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            columns = tuple(reader.fieldnames or ())
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            self._invalid_upload("El archivo CSV está corrupto.", reason="corrupt_file")
            raise AssertionError("unreachable") from exc
        if not columns or not rows:
            self._invalid_upload("El archivo no contiene registros.", reason="no_records")
        if any(column is None or not column.strip() for column in columns):
            self._invalid_upload("El encabezado contiene columnas vacías.", reason="invalid_header")
        return columns, rows

    def _validate_rows(self, rows: list[dict[str, str]], reference_month: str) -> None:
        temporal = self._contract.temporal_column
        if temporal:
            invalid = [
                index + 2
                for index, row in enumerate(rows)
                if not _MONTH_PATTERN.fullmatch(row.get(temporal, ""))
                or row[temporal] > reference_month
            ]
            if invalid:
                self._invalid_upload(
                    "El período del archivo no coincide con reference_month.",
                    reason="reference_month_mismatch",
                    rows=invalid[:20],
                )

        municipality = self._contract.municipality_column
        if municipality:
            observed = {row.get(municipality, "") for row in rows}
            unsupported = sorted(observed - set(self._contract.supported_municipalities))
            missing = sorted(set(self._contract.required_municipalities) - observed)
            if unsupported or missing:
                self._invalid_upload(
                    "Los municipios no cumplen el contrato habilitado.",
                    reason="municipality_contract_violation",
                    unsupported=unsupported,
                    missing=missing,
                )

    @staticmethod
    def _invalid_upload(message: str, **details: object) -> None:
        raise ContractError(ErrorCode.INVALID_UPLOAD, message, details=dict(details))
