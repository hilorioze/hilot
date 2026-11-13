from collections.abc import AsyncGenerator

from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3.client import S3Client

from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.infrastructure.database.sql.repositories.stored_file import SQLStoredFileRepository
from hilot.infrastructure.s3.client import create_s3_client
from hilot.infrastructure.s3.file_storage import S3FileStorage
from hilot.main.config.s3 import S3Config


class S3Provider(Provider):
    config = from_context(provides=S3Config, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def get_client(self, config: S3Config) -> AsyncGenerator[S3Client]:
        async with create_s3_client(
            endpoint_url=config.endpoint_url,
            region=config.region,
            access_key_id=config.access_key_id,
            secret_access_key=config.secret_access_key.get_secret_value(),
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    def get_file_storage(self, *, client: S3Client, config: S3Config) -> FileStorage:
        return S3FileStorage(client=client, bucket=config.bucket)


class StoredFileProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def get_stored_file_repository(
        self, *, session: AsyncSession, config: S3Config
    ) -> StoredFileRepository:
        return SQLStoredFileRepository(session=session, reuse_period=config.reuse_period)
