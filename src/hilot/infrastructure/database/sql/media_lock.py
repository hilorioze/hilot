from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import override

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from hilot.domain.interfaces.adapters.media_lock import MediaLock
from hilot.domain.value_objects.media import MediaKey


class SQLMediaLock(MediaLock):
    def __init__(self, *, engine: AsyncEngine) -> None:
        self._engine: AsyncEngine = engine

    @override
    @asynccontextmanager
    async def acquire(self, media_key: MediaKey) -> AsyncGenerator[None]:
        # the lock lasts until the transaction ends, and a worker that dies releases it with its connection
        async with self._engine.begin() as connection:
            await connection.execute(
                select(
                    func.pg_advisory_xact_lock(
                        # a collision of the hashes only makes two media wait for each other
                        func.hashtextextended(f"{media_key.extractor}:{media_key.media_id}", 0)
                    )
                )
            )

            yield
