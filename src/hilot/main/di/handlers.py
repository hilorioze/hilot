from dishka import AsyncContainer, Provider, Scope, decorate, from_context
from pyrogram import Client

from hilot.main.config.worker import BotConfig
from hilot.presentation.telegram.filters import RecentFilter
from hilot.presentation.telegram.handlers import router


class HandlerProvider(Provider):
    config = from_context(provides=BotConfig, scope=Scope.APP)

    @decorate
    def add_handlers(
        self, *, client: Client, container: AsyncContainer, config: BotConfig
    ) -> Client:
        # add the handlers before the client starts, so they get the messages it catches up on
        router.register(
            client=client, container=container, filters=RecentFilter(config.max_message_age)
        )

        return client
