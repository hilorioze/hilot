import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.cleanup.delete_expired import DeleteExpiredData

from .config.database import DatabaseConfig
from .config.loader import load_config
from .config.schemas import CleanupSchema
from .config.stored_file import StoredFileConfig
from .di.database import DatabaseProvider
from .di.stored_file import StoredFileProvider
from .di.watermarks import CachedWatermarkCheckProvider


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(DeleteExpiredData)


async def run() -> None:
    schema: CleanupSchema = load_config(schema=CleanupSchema)

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        StoredFileProvider(),
        CachedWatermarkCheckProvider(),
        _InteractorProvider(),
        context={DatabaseConfig: schema.database, StoredFileConfig: schema.stored_file},
    )

    async with container() as request_container:
        interactor: DeleteExpiredData = await request_container.get(DeleteExpiredData)

        await interactor()

    await container.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
