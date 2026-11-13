import asyncio
from collections.abc import AsyncGenerator
from functools import partial
from typing import ClassVar, override

from nats.aio.msg import Msg
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.api import ConsumerConfig, RetentionPolicy, StreamConfig
from taskiq import AckableMessage, BrokerMessage
from taskiq_nats import PullBasedJetStreamBroker

from .routes import Route


class RoutingJetStreamBroker(PullBasedJetStreamBroker):
    _STREAM_NAME: ClassVar[str] = "hilot"

    # a crashed worker's task goes to another one after this long without an ack
    _ACK_WAIT: ClassVar[float] = 30

    def __init__(self, *, servers: list[str], token: str, route: Route) -> None:
        super().__init__(
            servers=servers,
            token=token,
            subject=route.subject,
            stream_name=self._STREAM_NAME,
            durable=route.durable,
            stream_config=StreamConfig(
                subjects=[f"{self._STREAM_NAME}.>"], retention=RetentionPolicy.WORK_QUEUE
            ),
            consumer_config=ConsumerConfig(
                durable_name=route.durable, filter_subject=route.subject, ack_wait=self._ACK_WAIT
            ),
        )

    @override
    async def kick(self, message: BrokerMessage) -> None:
        # publish to the subject of the task's route: `self.subject` is the one this process consumes
        await self.js.publish(message.labels["subject"], payload=message.message)

    @override
    async def listen(self) -> AsyncGenerator[AckableMessage]:
        while True:
            try:
                messages: list[Msg] = await self.consumer.fetch(
                    batch=self.pull_consume_batch, timeout=self.pull_consume_timeout
                )
            except NatsTimeoutError:
                continue

            for message in messages:
                heartbeat: asyncio.Task[None] = asyncio.create_task(self._send_heartbeats(message))

                yield AckableMessage(
                    data=message.data, ack=partial(self._ack, message=message, heartbeat=heartbeat)
                )

    async def _send_heartbeats(self, message: Msg) -> None:
        while True:
            await asyncio.sleep(self._ACK_WAIT / 2)
            # keep jetstream from redelivering a message while its task runs
            await message.in_progress()

    @staticmethod
    async def _ack(*, message: Msg, heartbeat: asyncio.Task[None]) -> None:
        heartbeat.cancel()

        await message.ack()
