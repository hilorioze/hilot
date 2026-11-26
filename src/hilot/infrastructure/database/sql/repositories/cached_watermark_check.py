from datetime import datetime
from typing import override

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.interfaces.repositories.cached_watermark_check import (
    CachedWatermarkCheckRepository,
)
from hilot.domain.value_objects.media import ContentHash
from hilot.infrastructure.database.sql.converters import (
    convert_cached_watermark_check_entity_to_row,
    convert_cached_watermark_check_model_to_entity,
)
from hilot.infrastructure.database.sql.models.cached_watermark_check import (
    CachedWatermarkCheckModel,
)
from hilot.infrastructure.database.sql.upsert import upsert


class SQLCachedWatermarkCheckRepository(CachedWatermarkCheckRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get(self, content_hash: ContentHash) -> CachedWatermarkCheck | None:
        model: CachedWatermarkCheckModel | None = await self._session.get(
            CachedWatermarkCheckModel, content_hash
        )

        if model is None:
            return None

        return convert_cached_watermark_check_model_to_entity(model)

    @override
    async def save(self, cached_watermark_check: CachedWatermarkCheck) -> None:
        await upsert(
            session=self._session,
            model=CachedWatermarkCheckModel,
            rows=[convert_cached_watermark_check_entity_to_row(cached_watermark_check)],
        )

    @override
    async def delete_expired(self, now: datetime) -> None:
        await self._session.execute(
            delete(CachedWatermarkCheckModel).where(CachedWatermarkCheckModel.expires_at <= now)
        )
