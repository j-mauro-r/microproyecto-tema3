"""Persistence ports reserved for HU006; HU005 supplies no implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from api.app.orchestration.monthly import MonthlyRunResult, PredictionSnapshotCandidate


class RunRepository(Protocol):
    def find_by_idempotency_key(self, key: str) -> MonthlyRunResult | None: ...

    def get(self, run_id: str) -> MonthlyRunResult | None: ...

    def save(self, result: MonthlyRunResult) -> None: ...

    def mark_completed(self, run_id: str, completed_at: object) -> None: ...


class PredictionRepository(Protocol):
    def save_snapshot(self, snapshot: PredictionSnapshotCandidate) -> None: ...

    def get_by_run_id(self, run_id: str) -> PredictionSnapshotCandidate | None: ...
