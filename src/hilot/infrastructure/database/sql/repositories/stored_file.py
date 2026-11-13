from datetime import timedelta
from typing import override

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.value_objects.media import MediaKey
from hilot.infrastructure.database.sql.converters import (
    convert_stored_file_entity_to_row,
    convert_stored_file_model_to_entity,
)
from hilot.infrastructure.database.sql.models.stored_file import StoredFileModel


class SQLStoredFileRepository(StoredFileRepository):
    def __init__(self, *, session: AsyncSession, reuse_period: timedelta) -> None:
        self._session: AsyncSession = session
        self._reuse_period: timedelta = reuse_period

    @override
    async def get(self, media_key: MediaKey) -> StoredFile | None:
        model: StoredFileModel | None = await self._session.scalar(
            select(StoredFileModel).where(
                StoredFileModel.extractor == media_key.extractor,
                StoredFileModel.media_id == media_key.media_id,
                # `reuse_period` ends before the file storage expires the file
                StoredFileModel.stored_at > func.now() - self._reuse_period,
            )
        )

        if model is None:
            return None

        return convert_stored_file_model_to_entity(model)

    @override
    async def save(self, stored_file: StoredFile) -> None:
        statement: Insert = insert(StoredFileModel).values(
            convert_stored_file_entity_to_row(stored_file)
        )

        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[StoredFileModel.extractor, StoredFileModel.media_id],
                set_={
                    column.name: column for column in statement.excluded if not column.primary_key
                },
                # a file sent again keeps its time: the file storage expires it from its upload
                where=StoredFileModel.storage_key != statement.excluded.storage_key,
            )
        )
