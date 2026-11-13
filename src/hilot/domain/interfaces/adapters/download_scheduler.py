from typing import Protocol

from hilot.domain.value_objects.download import DownloadRequest


class DownloadScheduler(Protocol):
    async def schedule_download(self, request: DownloadRequest) -> None: ...
