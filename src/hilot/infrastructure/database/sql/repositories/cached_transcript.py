from typing import override

from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.cached_transcript import CachedTranscript
from hilot.domain.interfaces.repositories.cached_transcript import CachedTranscriptRepository
from hilot.domain.value_objects.media import FileUniqueId
from hilot.infrastructure.database.sql.converters import (
    convert_cached_transcript_entity_to_row,
    convert_cached_transcript_model_to_entity,
)
from hilot.infrastructure.database.sql.models.cached_transcript import CachedTranscriptModel
from hilot.infrastructure.database.sql.upsert import upsert


class SQLCachedTranscriptRepository(CachedTranscriptRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get(self, file_unique_id: FileUniqueId) -> CachedTranscript | None:
        model: CachedTranscriptModel | None = await self._session.get(
            CachedTranscriptModel, file_unique_id
        )

        if model is None:
            return None

        return convert_cached_transcript_model_to_entity(model)

    @override
    async def save(self, cached_transcript: CachedTranscript) -> None:
        await upsert(
            session=self._session,
            model=CachedTranscriptModel,
            rows=[convert_cached_transcript_entity_to_row(cached_transcript)],
        )
