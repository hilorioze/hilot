from dataclasses import dataclass

from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.value_objects.download import DownloadRequest, DownloadResult, Failure


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportFailureDTO:
    request: DownloadRequest


class ReportFailure:
    def __init__(self, *, delivery_scheduler: DeliveryScheduler) -> None:
        self._delivery_scheduler: DeliveryScheduler = delivery_scheduler

    async def __call__(self, data: ReportFailureDTO) -> None:
        result: DownloadResult = DownloadResult(
            request=data.request,
            media=[],
            failures=[Failure.from_bug(link) for link in data.request.links],
        )
        await self._delivery_scheduler.schedule_delivery(result)
