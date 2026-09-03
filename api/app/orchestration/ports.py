"""Persistence ports reserved for HU006; HU005 supplies no implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from api.app.orchestration.monthly import MonthlyRunResult, PredictionSnapshotCandidate


class RunRepository(Protocol):
    def find_by_idempotency_key(self, key: str) -> MonthlyRunResult | None: ...

    def save_run(self, result: MonthlyRunResult) -> None: ...


class PredictionRepository(Protocol):
    def save_snapshot(self, snapshot: PredictionSnapshotCandidate) -> None: ...
