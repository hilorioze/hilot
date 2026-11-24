from typing import Protocol

from hilot.domain.value_objects.watermark import WatermarkCheckRequest, WatermarkReply


class WatermarkCheckScheduler(Protocol):
    async def schedule_check(self, request: WatermarkCheckRequest) -> None: ...


class WatermarkReplyScheduler(Protocol):
    async def schedule_reply(self, reply: WatermarkReply) -> None: ...
