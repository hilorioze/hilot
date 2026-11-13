import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.media.report_failure import ReportFailure
from hilot.application.media.transcode import TranscodeMedia
from hilot.infrastructure.queue.routes import TRANSCODE_ROUTE, Route
from hilot.presentation.taskiq.media import transcode_media

from .config.disk import DiskConfig
from .config.loader import load_config
from .config.nats import NatsConfig
from .config.s3 import S3Config
from .config.schemas import TranscoderSchema
from .di.media import DiskSpaceProvider, FfmpegProvider, WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(TranscodeMedia, ReportFailure)


async def run() -> None:
    schema: TranscoderSchema = load_config(schema=TranscoderSchema, secrets_scope="transcoder")

    container: AsyncContainer = make_async_container(
        S3Provider(),
        QueueProvider(),
        WorkspaceProvider(),
        DiskSpaceProvider(),
        FfmpegProvider(),
        _InteractorProvider(),
        context={
            S3Config: schema.s3,
            NatsConfig: schema.nats,
            Route: TRANSCODE_ROUTE,
            DiskConfig: schema.disk,
        },
    )

    await run_worker(container=container, config=schema.transcoder, task=transcode_media)

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
