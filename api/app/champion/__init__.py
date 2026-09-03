"""Framework-independent Champion integration boundary for HU004."""

from api.app.champion.adapter import (
    ChampionLoader,
    ChampionRuntime,
    LazyChampionAdapter,
    MUNICIPALITY_NAMES,
    NativePrediction,
    build_champion_adapter,
)
from api.app.champion.models import ChampionMetadata, ChampionOutput, ChampionPrediction
from api.app.champion.materialized import (
    MaterializedChampionPrediction,
    MaterializedChampionResult,
    MaterializedOutputAdapter,
)
from api.app.champion.port import ChampionAdapter
from api.app.champion.provider import (
    ChampionExecutionContext,
    ChampionOutputProvider,
    ChampionProviderStrategy,
    ExecutableChampionProvider,
    MaterializedChampionProvider,
    build_champion_output_provider,
)
from api.app.champion.service import (
    CallableMaterializedChampionResultProvider,
    ChampionInputProvider,
    ChampionOperationalContext,
    ChampionService,
    MaterializedChampionResultProvider,
    ValidatedUploadChampionInputProvider,
    build_champion_service,
)

__all__ = [
    "ChampionAdapter",
    "ChampionLoader",
    "ChampionMetadata",
    "ChampionOutput",
    "ChampionOutputProvider",
    "ChampionPrediction",
    "ChampionExecutionContext",
    "ChampionProviderStrategy",
    "ChampionOperationalContext",
    "ChampionService",
    "ChampionInputProvider",
    "ChampionRuntime",
    "LazyChampionAdapter",
    "MUNICIPALITY_NAMES",
    "MaterializedChampionPrediction",
    "MaterializedChampionResult",
    "MaterializedOutputAdapter",
    "ExecutableChampionProvider",
    "MaterializedChampionProvider",
    "MaterializedChampionResultProvider",
    "CallableMaterializedChampionResultProvider",
    "NativePrediction",
    "build_champion_adapter",
    "build_champion_output_provider",
    "ValidatedUploadChampionInputProvider",
    "build_champion_service",
]
