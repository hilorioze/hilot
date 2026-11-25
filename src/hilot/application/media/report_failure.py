from dataclasses import dataclass

from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkReplyScheduler
from hilot.domain.value_objects.download import (
    DownloadPurpose,
    DownloadRequest,
    DownloadResult,
    Failure,
)
from hilot.domain.value_objects.watermark import WatermarkReply


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportFailureDTO:
    request: DownloadRequest


class ReportFailure:
    def __init__(
        self,
        *,
        delivery_scheduler: DeliveryScheduler,
        watermark_reply_scheduler: WatermarkReplyScheduler,
    ) -> None:
        self._delivery_scheduler: DeliveryScheduler = delivery_scheduler
        self._watermark_reply_scheduler: WatermarkReplyScheduler = watermark_reply_scheduler

    async def __call__(self, data: ReportFailureDTO) -> None:
        if data.request.purpose == DownloadPurpose.WATERMARK_CHECK:
            await self._watermark_reply_scheduler.schedule_reply(
                WatermarkReply.from_bug(data.request.source)
            )

            return

        result: DownloadResult = DownloadResult(
            request=data.request,
            media=[],
            failures=[Failure.from_bug(link) for link in data.request.links],
        )
        await self._delivery_scheduler.schedule_delivery(result)
