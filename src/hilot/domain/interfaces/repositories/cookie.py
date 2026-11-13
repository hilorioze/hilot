from typing import Protocol

from hilot.domain.value_objects.cookie import Cookie


class CookieRepository(Protocol):
    async def get_all(self) -> list[Cookie]: ...

    async def save(self, cookies: list[Cookie]) -> None: ...

    async def delete(self, cookies: list[Cookie]) -> None: ...
