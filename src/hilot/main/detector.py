import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.watermarks.check import CheckWatermark
from hilot.application.watermarks.report_failure import ReportWatermarkFailure
from hilot.infrastructure.queue.routes import WATERMARK_ROUTE, Route
from hilot.presentation.taskiq.watermarks import check_watermark

from .config.loader import load_config
from .config.nats import NatsConfig
from .config.s3 import S3Config
from .config.schemas import DetectorSchema
from .config.synthid import SynthIdConfig
from .config.worker import DetectorConfig
from .di.media import WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider
from .di.watermarks import WatermarkDetectorProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(CheckWatermark, ReportWatermarkFailure)


async def run() -> None:
    schema: DetectorSchema = load_config(schema=DetectorSchema, secrets_scope="detector")

    container: AsyncContainer = make_async_container(
        S3Provider(),
        QueueProvider(),
        WorkspaceProvider(),
        WatermarkDetectorProvider(),
        _InteractorProvider(),
        context={
            S3Config: schema.s3,
            NatsConfig: schema.nats,
            Route: WATERMARK_ROUTE,
            DetectorConfig: schema.detector,
            SynthIdConfig: schema.synthid,
        },
    )

    await run_worker(
        container=container, config=schema.detector, tasks={WATERMARK_ROUTE: check_watermark}
    )

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
