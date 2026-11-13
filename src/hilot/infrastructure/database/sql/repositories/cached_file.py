from typing import override

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.interfaces.repositories.cached_file import CachedFileRepository
from hilot.domain.value_objects.media import MediaKey
from hilot.domain.value_objects.message import AccountId
from hilot.infrastructure.database.sql.converters import (
    convert_cached_file_entity_to_row,
    convert_cached_file_model_to_entity,
)
from hilot.infrastructure.database.sql.models.cached_file import CachedFileModel
from hilot.infrastructure.database.sql.upsert import upsert


class SQLCachedFileRepository(CachedFileRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get(self, *, account_id: AccountId, media_key: MediaKey) -> CachedFile | None:
        model: CachedFileModel | None = await self._session.get(
            CachedFileModel, (account_id, media_key.extractor, media_key.media_id)
        )

        if model is None:
            return None

        return convert_cached_file_model_to_entity(model)

    @override
    async def save(self, cached_file: CachedFile) -> None:
        await upsert(
            session=self._session,
            model=CachedFileModel,
            rows=[convert_cached_file_entity_to_row(cached_file)],
        )

    @override
    async def delete(self, cached_file: CachedFile) -> None:
        await self._session.execute(
            delete(CachedFileModel).where(
                CachedFileModel.account_id == cached_file.account_id,
                CachedFileModel.extractor == cached_file.media_key.extractor,
                CachedFileModel.media_id == cached_file.media_key.media_id,
            ),
        )
