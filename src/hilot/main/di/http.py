from collections.abc import AsyncGenerator

from aiohttp import ClientSession
from dishka import Provider, Scope, provide

from hilot.domain.interfaces.adapters.redirect_reader import RedirectReader
from hilot.infrastructure.http.client import create_http_session
from hilot.infrastructure.http.redirect_reader import HttpRedirectReader


class RedirectReaderProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_session(self) -> AsyncGenerator[ClientSession]:
        async with create_http_session() as session:
            yield session

    @provide(scope=Scope.APP)
    def get_redirect_reader(self, session: ClientSession) -> RedirectReader:
        return HttpRedirectReader(session=session)
