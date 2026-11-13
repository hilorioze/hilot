from typing import Any, override

from adaptix import Retort
from taskiq import AsyncBroker
from taskiq.kicker import AsyncKicker

from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.transcode_scheduler import TranscodeScheduler
from hilot.domain.value_objects.download import DownloadRequest, DownloadResult

from .routes import (
    DOWNLOAD_ROUTE,
    TRANSCODE_ROUTE,
    Route,
    get_delivery_route,
)


class TaskiqScheduler(DownloadScheduler, TranscodeScheduler, DeliveryScheduler):
    def __init__(self, *, broker: AsyncBroker, retort: Retort) -> None:
        self._broker: AsyncBroker = broker
        self._retort: Retort = retort

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

    async def _kick(self, *, route: Route, payload: dict[str, Any]) -> None:
        await AsyncKicker(
            task_name=route.task_name, broker=self._broker, labels={"subject": route.subject}
        ).kiq(payload=payload)
