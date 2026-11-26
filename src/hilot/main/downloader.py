import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.media.download import DownloadMedia
from hilot.application.media.report_failure import ReportFailure
from hilot.infrastructure.queue.routes import DOWNLOAD_ROUTE, Route
from hilot.presentation.taskiq.media import download_media

from .config.database import DatabaseConfig
from .config.disk import DiskConfig
from .config.encryption import EncryptionConfig
from .config.loader import load_config
from .config.nats import NATSConfig
from .config.s3 import S3Config
from .config.schemas import DownloaderSchema
from .config.stored_file import StoredFileConfig
from .config.worker import DownloaderConfig
from .di.cookies import CookiesProvider
from .di.database import DatabaseProvider
from .di.encryption import EncryptionProvider
from .di.extractors import MediaExtractorProvider
from .di.media import DiskSpaceProvider, FfmpegProvider, WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider
from .di.stored_file import StoredFileProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(DownloadMedia, ReportFailure)


async def run() -> None:
    schema: DownloaderSchema = load_config(schema=DownloaderSchema, secrets_scope="downloader")

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        EncryptionProvider(),
        CookiesProvider(),
        S3Provider(),
        StoredFileProvider(),
        QueueProvider(),
        MediaExtractorProvider(),
        WorkspaceProvider(),
        DiskSpaceProvider(),
        FfmpegProvider(),
        _InteractorProvider(),
        context={
            DatabaseConfig: schema.database,
            EncryptionConfig: schema.encryption,
            S3Config: schema.s3,
            StoredFileConfig: schema.stored_file,
            NATSConfig: schema.nats,
            Route: DOWNLOAD_ROUTE,
            DownloaderConfig: schema.downloader,
            DiskConfig: schema.disk,
        },
    )

    await run_worker(
        container=container, config=schema.downloader, tasks={DOWNLOAD_ROUTE: download_media}
    )

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
