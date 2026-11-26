from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.infrastructure.database.sql.repositories.stored_file import SQLStoredFileRepository
from hilot.main.config.stored_file import StoredFileConfig


class StoredFileProvider(Provider):
    config = from_context(provides=StoredFileConfig, scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    def get_stored_file_repository(
        self, *, session: AsyncSession, config: StoredFileConfig
    ) -> StoredFileRepository:
        return SQLStoredFileRepository(session=session, reuse_period=config.reuse_period)
