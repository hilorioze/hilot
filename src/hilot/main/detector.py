import asyncio
from functools import partial

from aiohttp import ClientSession
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.watermarks.add_account import AddDetectionAccount
from hilot.application.watermarks.check import CheckWatermark
from hilot.application.watermarks.report_failure import ReportWatermarkFailure
from hilot.infrastructure.queue.routes import WATERMARK_ROUTE, Route
from hilot.infrastructure.synthid.login_watcher import SynthIDLoginWatcher
from hilot.presentation.browser.logins import add_detection_account
from hilot.presentation.taskiq.watermarks import check_watermark

from .config.database import DatabaseConfig
from .config.encryption import EncryptionConfig
from .config.loader import load_config
from .config.nats import NATSConfig
from .config.s3 import S3Config
from .config.schemas import DetectorSchema
from .config.worker import DetectorConfig
from .di.database import DatabaseProvider
from .di.encryption import EncryptionProvider
from .di.media import WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider
from .di.watermarks import (
    DetectableMediaMatcherProvider,
    DetectionAccountProvider,
    WatermarkDetectorProvider,
)
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(CheckWatermark, ReportWatermarkFailure, AddDetectionAccount)


async def run() -> None:
    schema: DetectorSchema = load_config(schema=DetectorSchema, secrets_scope="detector")

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        EncryptionProvider(),
        S3Provider(),
        QueueProvider(),
        WorkspaceProvider(),
        DetectableMediaMatcherProvider(),
        WatermarkDetectorProvider(),
        DetectionAccountProvider(),
        _InteractorProvider(),
        context={
            DatabaseConfig: schema.database,
            EncryptionConfig: schema.encryption,
            S3Config: schema.s3,
            NATSConfig: schema.nats,
            Route: WATERMARK_ROUTE,
            DetectorConfig: schema.detector,
        },
    )

    # the accounts come from signing in to synthid.com in the browser
    async with SynthIDLoginWatcher.open(
        session=await container.get(ClientSession),
        cdp_url=schema.detector.browser_url,
        on_login=partial(add_detection_account, container=container),
    ):
        await run_worker(
            container=container, config=schema.detector, tasks={WATERMARK_ROUTE: check_watermark}
        )

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
