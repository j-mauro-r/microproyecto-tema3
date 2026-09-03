"""Pure adaptation from a validated monthly upload to the Champion input contract."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import NoReturn

from api.app.domain.champion_feature_contract import (
    CHAMPION_FEATURE_CONTRACT_SHA256,
    CHAMPION_FEATURE_CONTRACT_VERSION,
    CHAMPION_FEATURES,
)
from api.app.domain.errors import ContractError
from api.app.domain.monthly_uploads import ValidatedMonthlyUpload
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus

MUNICIPALITY_ORDER: tuple[str, ...] = ("68001", "76001")
_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True, slots=True)
class ChampionInput:
    """Framework-independent, positionally ordered input for HU004."""

    reference_month: str
    municipalities: tuple[str, ...]
    feature_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]
    feature_contract_version: str
    feature_contract_sha256: str
    source_file_sha256: str


class ChampionInputBuilder:
    """Select and order already-computed features without engineering them."""

    def build(self, upload: ValidatedMonthlyUpload) -> ChampionInput:
        reference_year, reference_month = self._reference_period(upload.reference_month)
        rows_by_municipality = self._index_rows(upload.rows)
        numeric_rows = tuple(
            self._numeric_row(
                rows_by_municipality[municipality],
                municipality=municipality,
                reference_year=reference_year,
                reference_month=reference_month,
            )
            for municipality in MUNICIPALITY_ORDER
        )
        return ChampionInput(
            reference_month=upload.reference_month,
            municipalities=MUNICIPALITY_ORDER,
            feature_names=CHAMPION_FEATURES,
            rows=numeric_rows,
            feature_contract_version=CHAMPION_FEATURE_CONTRACT_VERSION,
            feature_contract_sha256=CHAMPION_FEATURE_CONTRACT_SHA256,
            source_file_sha256=upload.metadata.sha256,
        )

    def _index_rows(
        self, rows: tuple[dict[str, str], ...]
    ) -> dict[str, dict[str, str]]:
        indexed: dict[str, dict[str, str]] = {}
        duplicates: list[str] = []
        for row in rows:
            municipality = row.get("divipola", "")
            if municipality in indexed:
                duplicates.append(municipality)
            indexed[municipality] = row

        observed = set(indexed)
        expected = set(MUNICIPALITY_ORDER)
        if duplicates:
            self._invalid(
                "El input contiene municipios duplicados.",
                reason="duplicate_municipality",
                municipalities=sorted(set(duplicates)),
            )
        if observed != expected or len(rows) != len(MUNICIPALITY_ORDER):
            self._invalid(
                "El input debe contener exactamente Bucaramanga y Cali.",
                reason="municipality_contract_violation",
                missing=sorted(expected - observed),
                unexpected=sorted(observed - expected),
            )
        return indexed

    def _numeric_row(
        self,
        row: dict[str, str],
        *,
        municipality: str,
        reference_year: int,
        reference_month: int,
    ) -> tuple[float, ...]:
        if row.get("anio") != str(reference_year) or not self._month_matches(
            row.get("mes", ""), reference_month
        ):
            self._invalid(
                "El periodo de la fila no coincide con reference_month.",
                reason="reference_month_mismatch",
                municipality=municipality,
            )

        missing = [feature for feature in CHAMPION_FEATURES if feature not in row]
        if missing:
            self._invalid(
                "Faltan features requeridas por el Champion.",
                reason="missing_features",
                municipality=municipality,
                features=missing,
            )

        values: list[float] = []
        invalid: list[str] = []
        for feature in CHAMPION_FEATURES:
            raw_value = row[feature]
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                invalid.append(feature)
                continue
            if not math.isfinite(value):
                invalid.append(feature)
                continue
            values.append(value)
        if invalid:
            self._invalid(
                "Las features del Champion deben ser numéricas y finitas.",
                reason="invalid_feature_values",
                municipality=municipality,
                features=invalid,
            )
        return tuple(values)

    @staticmethod
    def _reference_period(value: str) -> tuple[int, int]:
        match = _MONTH_PATTERN.fullmatch(value)
        if match is None:
            ChampionInputBuilder._invalid(
                "reference_month no cumple el contrato YYYY-MM.",
                reason="invalid_reference_month",
            )
        year, month = int(match.group(1)), int(match.group(2))
        try:
            date(year, month, 1)
        except ValueError as exc:
            try:
                ChampionInputBuilder._invalid(
                    "reference_month no representa un mes válido.",
                    reason="invalid_reference_month",
                )
            except ContractError as error:
                raise error from exc
        return year, month

    @staticmethod
    def _month_matches(raw_value: str, expected: int) -> bool:
        return bool(re.fullmatch(r"\d{1,2}", raw_value)) and int(raw_value) == expected

    @staticmethod
    def _invalid(message: str, **details: object) -> NoReturn:
        raise ContractError(
            ErrorCode.CHAMPION_INPUT_INVALID,
            message,
            stage=RunStatus.PREPARING,
            details=dict(details),
        )
