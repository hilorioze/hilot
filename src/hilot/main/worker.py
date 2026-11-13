import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any

from aiohttp import web
from dishka import AsyncContainer
from dishka.integrations.taskiq import setup_dishka
from taskiq import AsyncBroker
from taskiq.receiver import Receiver

from hilot.infrastructure.queue.middleware import FailureMetricMiddleware
from hilot.infrastructure.queue.routes import Route
from hilot.presentation.http.app import create_http_app

from .config.http import HttpConfig
from .config.worker import WorkerConfig


def configure_logging() -> None:
    # systemd adds the time to every line of the journal
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def run_worker(
    *,
    container: AsyncContainer,
    config: WorkerConfig,
    task: Callable[..., Coroutine[Any, Any, None]],
) -> None:
    broker: AsyncBroker = await container.get(AsyncBroker)
    route: Route = await container.get(Route)

    setup_dishka(container=container, broker=broker)
    broker.add_middlewares(FailureMetricMiddleware())
    broker.register_task(task, task_name=route.task_name)

    receiver: Receiver = Receiver(
        broker=broker,
        # the tasks load their payloads with adaptix
        validate_params=False,
        max_async_tasks=config.concurrency,
        # the container starts the broker as it first provides it, to kick tasks and to listen alike
        run_startup=False,
    )

    async with _serve_http(config.http):
        await receiver.listen(_create_shutdown_event())


@asynccontextmanager
async def _serve_http(config: HttpConfig) -> AsyncGenerator[None]:
    # the health checks and the scrapes of prometheus would fill the journal with access logs
    runner: web.AppRunner = web.AppRunner(create_http_app(), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host=config.host, port=config.port).start()

    yield

    await runner.cleanup()


def _create_shutdown_event() -> asyncio.Event:
    shutdown: asyncio.Event = asyncio.Event()
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    # systemd stops a process with `SIGTERM`, a terminal with `SIGINT`
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, shutdown.set)

    return shutdown
