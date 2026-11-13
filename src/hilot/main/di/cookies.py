from cryptography.fernet import Fernet, MultiFernet
from dishka import Provider, Scope, from_context, provide

from hilot.domain.interfaces.repositories.cookie import CookieRepository
from hilot.infrastructure.database.sql.repositories.cookie import SQLCookieRepository
from hilot.main.config.cookies import CookiesConfig


class CookiesProvider(Provider):
    config = from_context(provides=CookiesConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def get_fernet(self, config: CookiesConfig) -> MultiFernet:
        return MultiFernet([Fernet(key.get_secret_value()) for key in config.keys])

    cookie_repository = provide(
        SQLCookieRepository, provides=CookieRepository, scope=Scope.REQUEST
    )
