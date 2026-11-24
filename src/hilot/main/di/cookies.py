from dishka import Provider, Scope, provide

from hilot.domain.interfaces.repositories.cookie import CookieRepository
from hilot.infrastructure.database.sql.repositories.cookie import SQLCookieRepository


class CookiesProvider(Provider):
    cookie_repository = provide(
        SQLCookieRepository, provides=CookieRepository, scope=Scope.REQUEST
    )
