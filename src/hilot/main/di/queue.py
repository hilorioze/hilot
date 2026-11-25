from collections.abc import AsyncGenerator

from adaptix import Retort
from dishka import AnyOf, Provider, Scope, from_context, provide
from taskiq import AsyncBroker

from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.preview_wait_scheduler import PreviewWaitScheduler
from hilot.domain.interfaces.adapters.transcode_scheduler import TranscodeScheduler
from hilot.domain.interfaces.adapters.transcription_scheduler import (
    TranscriptionReplyScheduler,
    TranscriptionScheduler,
)
from hilot.domain.interfaces.adapters.watermark_scheduler import (
    WatermarkCheckScheduler,
    WatermarkReplyScheduler,
)
from hilot.infrastructure.queue.broker import RoutingJetStreamBroker
from hilot.infrastructure.queue.routes import Route
from hilot.infrastructure.queue.scheduler import TaskiqScheduler
from hilot.main.config.nats import NATSConfig


class QueueProvider(Provider):
    config = from_context(provides=NATSConfig, scope=Scope.APP)

    route = from_context(provides=Route, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def get_broker(self, *, config: NATSConfig, route: Route) -> AsyncGenerator[AsyncBroker]:
        # a process consumes its own route and kicks the tasks of the others through the same broker
        broker: AsyncBroker = RoutingJetStreamBroker(
            servers=config.servers, token=config.token.get_secret_value(), route=route
        )

        await broker.startup()

        yield broker

        await broker.shutdown()

    @provide(scope=Scope.APP)
    def get_retort(self) -> Retort:
        return Retort()

    scheduler = provide(
        TaskiqScheduler,
        provides=AnyOf[
            PreviewWaitScheduler,
            DownloadScheduler,
            TranscodeScheduler,
            DeliveryScheduler,
            WatermarkCheckScheduler,
            WatermarkReplyScheduler,
            TranscriptionScheduler,
            TranscriptionReplyScheduler,
        ],
        scope=Scope.APP,
    )
