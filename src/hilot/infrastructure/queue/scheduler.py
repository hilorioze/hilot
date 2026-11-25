from typing import Any, override

from adaptix import Retort
from taskiq import AsyncBroker
from taskiq.kicker import AsyncKicker

from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.preview_wait_scheduler import PreviewWaitScheduler
from hilot.domain.interfaces.adapters.transcode_scheduler import TranscodeScheduler
from hilot.domain.interfaces.adapters.watermark_scheduler import (
    WatermarkCheckScheduler,
    WatermarkReplyScheduler,
)
from hilot.domain.value_objects.download import DownloadRequest, DownloadResult, PreviewWait
from hilot.domain.value_objects.watermark import WatermarkCheckRequest, WatermarkReply

from .routes import (
    DOWNLOAD_ROUTE,
    TRANSCODE_ROUTE,
    WATERMARK_ROUTE,
    Route,
    get_delivery_route,
    get_preview_wait_route,
    get_watermark_reply_route,
)


class TaskiqScheduler(
    PreviewWaitScheduler,
    DownloadScheduler,
    TranscodeScheduler,
    DeliveryScheduler,
    WatermarkCheckScheduler,
    WatermarkReplyScheduler,
):
    def __init__(self, *, broker: AsyncBroker, retort: Retort) -> None:
        self._broker: AsyncBroker = broker
        self._retort: Retort = retort

    @override
    async def schedule_preview_wait(self, wait: PreviewWait) -> None:
        await self._kick(
            route=get_preview_wait_route(wait.source.account_id), payload=self._retort.dump(wait)
        )

    @override
    async def schedule_download(self, request: DownloadRequest) -> None:
        await self._kick(route=DOWNLOAD_ROUTE, payload=self._retort.dump(request))

    @override
    async def schedule_transcode(self, result: DownloadResult) -> None:
        await self._kick(route=TRANSCODE_ROUTE, payload=self._retort.dump(result))

    @override
    async def schedule_delivery(self, result: DownloadResult) -> None:
        await self._kick(
            route=get_delivery_route(result.request.source.account_id),
            payload=self._retort.dump(result),
        )

    @override
    async def schedule_check(self, request: WatermarkCheckRequest) -> None:
        await self._kick(route=WATERMARK_ROUTE, payload=self._retort.dump(request))

    @override
    async def schedule_reply(self, reply: WatermarkReply) -> None:
        await self._kick(
            route=get_watermark_reply_route(reply.source.account_id),
            payload=self._retort.dump(reply),
        )

    async def _kick(self, *, route: Route, payload: dict[str, Any]) -> None:
        await AsyncKicker(
            task_name=route.task_name, broker=self._broker, labels={"subject": route.subject}
        ).kiq(payload=payload)
