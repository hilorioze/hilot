from collections.abc import AsyncGenerator

from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hilot.domain.interfaces.repositories.cached_file import CachedFileRepository
from hilot.domain.interfaces.repositories.delivered_part import DeliveredPartRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.infrastructure.database.sql.repositories.cached_file import SQLCachedFileRepository
from hilot.infrastructure.database.sql.repositories.delivered_part import (
    SQLDeliveredPartRepository,
)
from hilot.infrastructure.database.sql.unit_of_work import SQLUnitOfWork
from hilot.main.config.database import DatabaseConfig


class DatabaseProvider(Provider):
    config = from_context(provides=DatabaseConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def get_engine(self, config: DatabaseConfig) -> AsyncGenerator[AsyncEngine]:
        engine: AsyncEngine = create_async_engine(config.url)

        yield engine

        await engine.dispose()

    @provide(scope=Scope.APP)
    def get_session_maker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            engine,
            expire_on_commit=False,  # the entities stay readable after the transaction that loaded them
        )

    @provide(scope=Scope.REQUEST)
    async def get_session(
        self, session_maker: async_sessionmaker[AsyncSession]
    ) -> AsyncGenerator[AsyncSession]:
        async with session_maker() as session:
            yield session

    unit_of_work = provide(SQLUnitOfWork, provides=UnitOfWork, scope=Scope.REQUEST)

    cached_file_repository = provide(
        SQLCachedFileRepository, provides=CachedFileRepository, scope=Scope.REQUEST
    )
    delivered_part_repository = provide(
        SQLDeliveredPartRepository, provides=DeliveredPartRepository, scope=Scope.REQUEST
    )
