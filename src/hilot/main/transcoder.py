import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.media.report_failure import ReportFailure
from hilot.application.media.transcode import TranscodeMedia
from hilot.infrastructure.queue.routes import TRANSCODE_ROUTE, Route
from hilot.presentation.taskiq.media import transcode_media

from .config.database import DatabaseConfig
from .config.disk import DiskConfig
from .config.loader import load_config
from .config.nats import NATSConfig
from .config.s3 import S3Config
from .config.schemas import TranscoderSchema
from .di.database import DatabaseProvider
from .di.media import DiskSpaceProvider, FfmpegProvider, WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider, StoredFileProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(TranscodeMedia, ReportFailure)


async def run() -> None:
    schema: TranscoderSchema = load_config(schema=TranscoderSchema, secrets_scope="transcoder")

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        S3Provider(),
        StoredFileProvider(),
        QueueProvider(),
        WorkspaceProvider(),
        DiskSpaceProvider(),
        FfmpegProvider(),
        _InteractorProvider(),
        context={
            DatabaseConfig: schema.database,
            S3Config: schema.s3,
            NATSConfig: schema.nats,
            Route: TRANSCODE_ROUTE,
            DiskConfig: schema.disk,
        },
    )

    await run_worker(
        container=container, config=schema.transcoder, tasks={TRANSCODE_ROUTE: transcode_media}
    )

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
