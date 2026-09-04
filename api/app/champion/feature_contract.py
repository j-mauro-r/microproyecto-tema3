"""Shared HU004 gate between effective input and Champion metadata."""

from __future__ import annotations

from api.app.champion.models import ChampionMetadata
from api.app.domain.errors import ContractError
from api.app.schemas.errors import ErrorCode
from api.app.schemas.runs import RunStatus


def require_compatible_feature_contract(
    *,
    expected_version: str,
    expected_sha256: str,
    received: ChampionMetadata,
) -> None:
    """Reject a Champion output unless both feature-contract identifiers match."""

    if (
        received.feature_contract_version == expected_version
        and received.feature_contract_sha256 == expected_sha256
    ):
        return
    raise ContractError(
        ErrorCode.CHAMPION_INPUT_INVALID,
        "El input no es compatible con el contrato del Champion.",
        stage=RunStatus.INFERENCING,
        details={
            "reason": "feature_contract_mismatch",
            "expected_version": expected_version,
            "received_version": received.feature_contract_version,
            "expected_sha256": expected_sha256,
            "received_sha256": received.feature_contract_sha256,
        },
    )
