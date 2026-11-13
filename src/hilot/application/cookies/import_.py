from dataclasses import dataclass

from hilot.domain.interfaces.repositories.cookie import CookieRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.cookie import Cookie


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportCookiesDTO:
    cookies: list[Cookie]


class ImportCookies:
    def __init__(self, *, cookie_repository: CookieRepository, uow: UnitOfWork) -> None:
        self._cookie_repository: CookieRepository = cookie_repository
        self._uow: UnitOfWork = uow

    async def __call__(self, data: ImportCookiesDTO) -> None:
        domains: set[str] = {cookie.domain for cookie in data.cookies}

        async with self._uow:
            cookies: list[Cookie] = await self._cookie_repository.get_all()

            # a fresh login replaces every cookie of its site
            await self._cookie_repository.delete(
                [cookie for cookie in cookies if cookie.domain in domains]
            )

            await self._cookie_repository.save(data.cookies)
