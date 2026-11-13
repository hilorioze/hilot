from types import TracebackType
from typing import Self, override

from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.interfaces.unit_of_work import UnitOfWork


class SQLUnitOfWork(UnitOfWork):
    def __init__(self, *, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    @override
    async def __aenter__(self) -> Self:
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()
