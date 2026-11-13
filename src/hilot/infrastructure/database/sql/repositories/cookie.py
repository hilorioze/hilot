from typing import override

from cryptography.fernet import MultiFernet
from sqlalchemy import ScalarResult, delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.interfaces.repositories.cookie import CookieRepository
from hilot.domain.value_objects.cookie import Cookie
from hilot.infrastructure.database.sql.converters import (
    convert_cookie_entity_to_row,
    convert_cookie_model_to_entity,
)
from hilot.infrastructure.database.sql.models.cookie import CookieModel
from hilot.infrastructure.database.sql.upsert import upsert


class SQLCookieRepository(CookieRepository):
    def __init__(self, *, session: AsyncSession, fernet: MultiFernet) -> None:
        self._session: AsyncSession = session
        self._fernet: MultiFernet = fernet

    @override
    async def get_all(self) -> list[Cookie]:
        models: ScalarResult[CookieModel] = await self._session.scalars(select(CookieModel))

        return [
            convert_cookie_model_to_entity(
                model=model, value=self._fernet.decrypt(model.encrypted_value).decode()
            )
            for model in models
        ]

    @override
    async def save(self, cookies: list[Cookie]) -> None:
        await upsert(
            session=self._session,
            model=CookieModel,
            rows=[
                convert_cookie_entity_to_row(
                    cookie=cookie, encrypted_value=self._fernet.encrypt(cookie.value.encode())
                )
                for cookie in cookies
            ],
        )

    @override
    async def delete(self, cookies: list[Cookie]) -> None:
        await self._session.execute(
            delete(CookieModel).where(
                tuple_(CookieModel.domain, CookieModel.path, CookieModel.name).in_(
                    [(cookie.domain, cookie.path, cookie.name) for cookie in cookies]
                )
            )
        )
