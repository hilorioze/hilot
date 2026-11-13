from typing import Protocol

from hilot.domain.value_objects.download import DownloadResult


class DeliveryScheduler(Protocol):
    async def schedule_delivery(self, result: DownloadResult) -> None: ...
