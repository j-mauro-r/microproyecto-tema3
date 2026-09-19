"""Transactional promotion of HU005 results to durable COMPLETED runs."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Protocol

from api.app.domain.errors import ContractError
from api.app.orchestration.monthly import MonthlyRunResult
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


class PersistenceUnitOfWork(Protocol):
    runs: object
    predictions: object

    def __enter__(self) -> PersistenceUnitOfWork: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


class MonthlyRunPersistenceService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], PersistenceUnitOfWork],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def persist(self, result: MonthlyRunResult) -> MonthlyRunResult:
        if result.status is RunStatus.FAILED:
            return self._persist_failed(result)
        self._validate_ready(result)

        try:
            existing = self._find_existing(result.idempotency_key)
        except Exception as exc:
            raise self._failure() from exc
        if existing is not None:
            return existing
        try:
            with self._unit_of_work_factory() as uow:
                existing = uow.runs.find_by_idempotency_key(result.idempotency_key)
                if existing is not None:
                    return existing
                persisting = replace(
                    result,
                    status=RunStatus.PERSISTING,
                    stages=result.stages + (RunStatus.PERSISTING,),
                )
                uow.runs.save(persisting)
                uow.predictions.save_snapshot(result.snapshot)
                completed_at = self._clock()
                uow.runs.mark_completed(result.run_id, completed_at)
            persisted = self.get(result.run_id)
            if persisted is None or persisted.status is not RunStatus.COMPLETED:
                raise RuntimeError("committed run could not be recovered")
            return persisted
        except sqlite3.IntegrityError as exc:
            existing = self._find_existing(result.idempotency_key)
            if existing is not None:
                return existing
            raise self._failure() from exc
        except ContractError:
            raise
        except Exception as exc:
            raise self._failure() from exc

    def get(self, run_id: str) -> MonthlyRunResult | None:
        try:
            with self._unit_of_work_factory() as uow:
                return uow.runs.get(run_id)
        except Exception as exc:
            raise self._failure() from exc

    def get_snapshot(self, run_id: str):
        try:
            with self._unit_of_work_factory() as uow:
                return uow.predictions.get_by_run_id(run_id)
        except Exception as exc:
            raise self._failure() from exc

    def _persist_failed(self, result: MonthlyRunResult) -> MonthlyRunResult:
        if result.snapshot is not None:
            raise self._failure("failed_run_has_snapshot")
        try:
            with self._unit_of_work_factory() as uow:
                existing = uow.runs.get(result.run_id)
                if existing is not None:
                    return existing
                uow.runs.save(result)
            persisted = self.get(result.run_id)
            if persisted is None:
                raise RuntimeError("failed run could not be recovered")
            return persisted
        except ContractError:
            raise
        except Exception as exc:
            raise self._failure() from exc

    def _find_existing(self, key: str | None) -> MonthlyRunResult | None:
        if key is None:
            return None
        with self._unit_of_work_factory() as uow:
            existing = uow.runs.find_by_idempotency_key(key)
            return existing if existing and existing.status is RunStatus.COMPLETED else None

    @staticmethod
    def _validate_ready(result: MonthlyRunResult) -> None:
        if (
            result.status is not RunStatus.READY_TO_PERSIST
            or result.snapshot is None
            or result.idempotency_key is None
            or result.source_file_sha256 is None
            or result.champion_version is None
        ):
            raise MonthlyRunPersistenceService._failure("run_not_ready_to_persist")

    @staticmethod
    def _failure(reason: str = "sqlite_transaction_failed") -> ContractError:
        return ContractError(
            ErrorCode.PERSISTENCE_FAILED,
            "No fue posible persistir el run mensual.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            stage=RunStatus.PERSISTING,
            details={"reason": reason},
        )
