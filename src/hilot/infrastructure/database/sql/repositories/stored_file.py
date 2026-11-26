from datetime import UTC, datetime, timedelta
from typing import override

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.value_objects.media import MediaKey
from hilot.infrastructure.database.sql.converters import (
    convert_stored_file_entity_to_row,
    convert_stored_file_model_to_entity,
)
from hilot.infrastructure.database.sql.models.stored_file import StoredFileModel
from hilot.infrastructure.database.sql.upsert import upsert


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
                StoredFileModel.expires_at > func.now(),
            )
        )

        if model is None:
            return None

        return convert_stored_file_model_to_entity(model)

    @override
    async def save(self, stored_file: StoredFile) -> None:
        await upsert(
            session=self._session,
            model=StoredFileModel,
            rows=[
                convert_stored_file_entity_to_row(stored_file)
                | {"expires_at": datetime.now(UTC) + self._reuse_period}
            ],
        )

    @override
    async def delete_expired(self, now: datetime) -> None:
        await self._session.execute(
            delete(StoredFileModel).where(StoredFileModel.expires_at <= now)
        )
