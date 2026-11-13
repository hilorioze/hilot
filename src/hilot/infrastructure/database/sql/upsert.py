from typing import Any

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models.base import Base


async def upsert(*, session: AsyncSession, model: type[Base], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    statement: Insert = insert(model)

    # postgres can't update one row twice in a statement; keep the last row of each key
    unique_rows: dict[tuple[Any, ...], dict[str, Any]] = {
        tuple(row[column.name] for column in statement.table.primary_key): row for row in rows
    }

    statement = statement.values(list(unique_rows.values()))
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=inspect(model).primary_key,
            set_={column.name: column for column in statement.excluded if not column.primary_key},
        )
    )
