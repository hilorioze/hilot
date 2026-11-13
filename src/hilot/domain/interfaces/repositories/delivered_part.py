from typing import Protocol

from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.value_objects.message import SourceMessage


class DeliveredPartRepository(Protocol):
    async def get_all(self, source: SourceMessage) -> list[DeliveredPart]: ...

    async def add(self, delivered_part: DeliveredPart) -> None: ...
