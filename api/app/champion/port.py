"""Public Champion port. No ML framework types belong here."""

from typing import Protocol, runtime_checkable

from api.app.champion.models import ChampionMetadata, ChampionOutput
from api.app.domain.champion_input import ChampionInput


@runtime_checkable
class ChampionAdapter(Protocol):
    def metadata(self) -> ChampionMetadata: ...

    def predict(self, inference_input: ChampionInput) -> ChampionOutput: ...
