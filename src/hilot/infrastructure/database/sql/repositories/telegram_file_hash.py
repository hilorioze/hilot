from typing import override

from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.telegram_file_hash import TelegramFileHash
from hilot.domain.interfaces.repositories.telegram_file_hash import TelegramFileHashRepository
from hilot.domain.value_objects.media import FileUniqueId
from hilot.infrastructure.database.sql.converters import (
    convert_telegram_file_hash_entity_to_row,
    convert_telegram_file_hash_model_to_entity,
)
from hilot.infrastructure.database.sql.models.telegram_file_hash import TelegramFileHashModel
from hilot.infrastructure.database.sql.upsert import upsert


class SQLTelegramFileHashRepository(TelegramFileHashRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get(self, file_unique_id: FileUniqueId) -> TelegramFileHash | None:
        model: TelegramFileHashModel | None = await self._session.get(
            TelegramFileHashModel, file_unique_id
        )

        if model is None:
            return None

        return convert_telegram_file_hash_model_to_entity(model)

    @override
    async def save(self, telegram_file_hash: TelegramFileHash) -> None:
        await upsert(
            session=self._session,
            model=TelegramFileHashModel,
            rows=[convert_telegram_file_hash_entity_to_row(telegram_file_hash)],
        )
