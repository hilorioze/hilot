from typing import override

from sqlalchemy import ScalarResult, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.interfaces.repositories.delivered_part import DeliveredPartRepository
from hilot.domain.value_objects.message import SourceMessage
from hilot.infrastructure.database.sql.converters import (
    convert_delivered_part_entity_to_row,
    convert_delivered_part_model_to_entity,
)
from hilot.infrastructure.database.sql.models.delivered_part import DeliveredPartModel


class SQLDeliveredPartRepository(DeliveredPartRepository):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def get_all(self, source: SourceMessage) -> list[DeliveredPart]:
        models: ScalarResult[DeliveredPartModel] = await self._session.scalars(
            select(DeliveredPartModel).where(
                DeliveredPartModel.account_id == source.account_id,
                DeliveredPartModel.chat_id == source.chat_id,
                DeliveredPartModel.message_id == source.message_id,
            ),
        )

        return [convert_delivered_part_model_to_entity(model) for model in models]

    @override
    async def add(self, delivered_part: DeliveredPart) -> None:
        await self._session.execute(
            insert(DeliveredPartModel).values(
                convert_delivered_part_entity_to_row(delivered_part)
            ),
        )
