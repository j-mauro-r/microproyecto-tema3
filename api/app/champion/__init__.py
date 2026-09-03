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
from api.app.champion.port import ChampionAdapter

__all__ = [
    "ChampionAdapter",
    "ChampionLoader",
    "ChampionMetadata",
    "ChampionOutput",
    "ChampionPrediction",
    "ChampionRuntime",
    "LazyChampionAdapter",
    "MUNICIPALITY_NAMES",
    "NativePrediction",
    "build_champion_adapter",
]
