from typing import Protocol


class RedirectReader(Protocol):
    async def read_redirect(self, url: str) -> str | None: ...
