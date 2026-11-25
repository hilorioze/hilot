from typing import Protocol

from hilot.domain.value_objects.download import PreviewWait


class PreviewWaitScheduler(Protocol):
    async def schedule_preview_wait(self, wait: PreviewWait) -> None: ...
