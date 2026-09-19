"""Pure, offline validation for a monthly source-file upload."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath

from api.app.domain.errors import ContractError
from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_SOURCE,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
    IDENTIFIER_COLUMNS,
    PROHIBITED_INPUT_COLUMNS,
)
from api.app.schemas.errors import ErrorCode

_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True, slots=True)
class MonthlyUploadContract:
    """Approved single-month CSV contract for the BIOMAC microproject."""

    allowed_extensions: tuple[str, ...] = (".csv",)
    identifier_columns: tuple[str, ...] = IDENTIFIER_COLUMNS
    feature_columns: tuple[str, ...] = CHAMPION_FEATURES
    feature_contract_version: str = CHAMPION_FEATURE_CONTRACT_VERSION
    feature_contract_sha256: str = CHAMPION_FEATURE_CONTRACT_SHA256
    feature_contract_source: str = CHAMPION_FEATURE_CONTRACT_SOURCE
    prohibited_columns: frozenset[str] = PROHIBITED_INPUT_COLUMNS
    municipality_column: str = "divipola"
    year_column: str = "anio"
    month_column: str = "mes"
    required_municipalities: tuple[str, ...] = ("68001", "76001")
    supported_municipalities: tuple[str, ...] = ("68001", "76001")

    @property
    def required_columns(self) -> tuple[str, ...]:
        return self.identifier_columns + self.feature_columns


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
    rows: tuple[dict[str, str], ...]


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
        prohibited = sorted(set(columns) & self._contract.prohibited_columns)
        if prohibited:
            self._invalid_upload(
                "El archivo contiene columnas objetivo o futuras prohibidas.",
                reason="prohibited_columns",
                columns=prohibited,
            )
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
            rows=tuple(
                {column: row[column] for column in self._contract.required_columns}
                for row in rows
            ),
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
        if len(set(columns)) != len(columns):
            self._invalid_upload("El encabezado contiene columnas duplicadas.", reason="duplicate_header")
        if any(None in row for row in rows):
            self._invalid_upload("Una fila no coincide con el encabezado.", reason="invalid_row_shape")
        return columns, rows

    def _validate_rows(self, rows: list[dict[str, str]], reference_month: str) -> None:
        reference_year, reference_month_number = reference_month.split("-")
        invalid_period_rows: list[int] = []
        municipalities: list[str] = []

        for index, row in enumerate(rows, start=2):
            year = row.get(self._contract.year_column, "")
            month = row.get(self._contract.month_column, "")
            municipality = row.get(self._contract.municipality_column, "")
            if (
                not re.fullmatch(r"\d{4}", year)
                or not re.fullmatch(r"\d{1,2}", month)
                or not 1 <= int(month) <= 12
                or year != reference_year
                or int(month) != int(reference_month_number)
            ):
                invalid_period_rows.append(index)
            if not re.fullmatch(r"\d{5}", municipality):
                self._invalid_upload(
                    "DIVIPOLA debe ser un string de cinco dígitos.",
                    reason="invalid_divipola",
                    rows=[index],
                )
            municipalities.append(municipality)
            self._validate_numeric_features(row, index)

        if invalid_period_rows:
            self._invalid_upload(
                "Todas las filas deben coincidir exactamente con reference_month.",
                reason="reference_month_mismatch",
                rows=invalid_period_rows[:20],
            )

        duplicates = sorted(
            municipality for municipality in set(municipalities) if municipalities.count(municipality) > 1
        )
        observed = set(municipalities)
        unsupported = sorted(observed - set(self._contract.supported_municipalities))
        missing = sorted(set(self._contract.required_municipalities) - observed)
        if duplicates:
            self._invalid_upload(
                "Existe más de una fila para el mismo municipio y mes.",
                reason="duplicate_municipality_month",
                municipalities=duplicates,
            )
        if unsupported or missing or len(rows) != len(self._contract.required_municipalities):
            self._invalid_upload(
                "El archivo debe contener exactamente Bucaramanga y Cali.",
                reason="municipality_contract_violation",
                unsupported=unsupported,
                missing=missing,
            )

    def _validate_numeric_features(self, row: dict[str, str], row_number: int) -> None:
        invalid: list[str] = []
        for feature in self._contract.feature_columns:
            raw_value = row.get(feature, "").strip()
            try:
                value = float(raw_value)
            except ValueError:
                invalid.append(feature)
                continue
            if not math.isfinite(value):
                invalid.append(feature)
        if invalid:
            self._invalid_upload(
                "Las features requeridas deben ser numéricas, finitas y no nulas.",
                reason="invalid_numeric_features",
                row=row_number,
                columns=invalid,
            )

    @staticmethod
    def _invalid_upload(message: str, **details: object) -> None:
        raise ContractError(ErrorCode.INVALID_UPLOAD, message, details=dict(details))
