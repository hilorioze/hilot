from datetime import datetime
from typing import override

from cryptography.fernet import MultiFernet
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.cached_transcript import CachedTranscript
from hilot.domain.interfaces.repositories.cached_transcript import (
    CachedTranscriptExpiryRepository,
    CachedTranscriptRepository,
)
from hilot.domain.value_objects.media import FileUniqueId
from hilot.infrastructure.database.sql.converters import (
    convert_cached_transcript_entity_to_row,
    convert_cached_transcript_model_to_entity,
)
from hilot.infrastructure.database.sql.models.cached_transcript import CachedTranscriptModel
from hilot.infrastructure.database.sql.upsert import upsert


class SQLCachedTranscriptRepository(CachedTranscriptRepository):
    def __init__(self, *, session: AsyncSession, fernet: MultiFernet) -> None:
        self._session: AsyncSession = session
        self._fernet: MultiFernet = fernet

    @override
    async def get(self, file_unique_id: FileUniqueId) -> CachedTranscript | None:
        # an expired transcript counts as gone before the cleanup deletes it
        model: CachedTranscriptModel | None = await self._session.scalar(
            select(CachedTranscriptModel).where(
                CachedTranscriptModel.file_unique_id == file_unique_id,
                CachedTranscriptModel.expires_at > func.now(),
            )
        )

        if model is None:
            return None

        return convert_cached_transcript_model_to_entity(
            model=model, text=self._fernet.decrypt(model.encrypted_text).decode()
        )

    @override
    async def save(self, cached_transcript: CachedTranscript) -> None:
        await upsert(
            session=self._session,
            model=CachedTranscriptModel,
            rows=[
                convert_cached_transcript_entity_to_row(
                    cached_transcript=cached_transcript,
                    encrypted_text=self._fernet.encrypt(
                        cached_transcript.transcript.text.encode()
                    ),
                )
            ],
        )


class SQLCachedTranscriptExpiryRepository(CachedTranscriptExpiryRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def delete_expired(self, now: datetime) -> None:
        await self._session.execute(
            delete(CachedTranscriptModel).where(CachedTranscriptModel.expires_at <= now)
        )
