from typing import Protocol

from hilot.domain.value_objects.download import DownloadResult


class TranscodeScheduler(Protocol):
    async def schedule_transcode(self, result: DownloadResult) -> None: ...
