from dataclasses import dataclass

from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkReplyScheduler
from hilot.domain.value_objects.watermark import (
    WatermarkCheckRequest,
    WatermarkFailure,
    WatermarkReply,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportWatermarkFailureDTO:
    request: WatermarkCheckRequest


class ReportWatermarkFailure:
    def __init__(self, *, reply_scheduler: WatermarkReplyScheduler) -> None:
        self._reply_scheduler: WatermarkReplyScheduler = reply_scheduler

    async def __call__(self, data: ReportWatermarkFailureDTO) -> None:
        await self._reply_scheduler.schedule_reply(
            WatermarkReply(source=data.request.source, outcome=WatermarkFailure.BUG)
        )
