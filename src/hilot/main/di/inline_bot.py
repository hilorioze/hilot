from collections.abc import AsyncGenerator

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from dishka import AnyOf, Provider, Scope, from_context, provide
from pyrogram import Client
from sqlalchemy.ext.asyncio import AsyncSession

from hilot.domain.interfaces.adapters.messenger import (
    RichLimitReader,
    RichMediaUploader,
    RichReplier,
    RichSender,
)
from hilot.domain.interfaces.repositories.bot_file import BotFileRepository
from hilot.infrastructure.database.sql.repositories.bot_file import SQLBotFileRepository
from hilot.infrastructure.telegram.inline_bot import InlineBotRichMessenger
from hilot.main.config.inline_bot import InlineBotConfig
from hilot.main.config.telegram import TelegramConfig


class InlineBotProvider(Provider):
    config = from_context(provides=InlineBotConfig, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def get_bot(
        self, *, config: InlineBotConfig, telegram_config: TelegramConfig
    ) -> AsyncGenerator[Bot]:
        # the bot of an account on the test backend lives there too
        environment: str = "/test" if telegram_config.test_mode else ""
        bot: Bot = Bot(
            token=config.token.get_secret_value(),
            session=AiohttpSession(
                api=TelegramAPIServer(
                    base=f"{config.api_url}/bot{{token}}{environment}/{{method}}",
                    file=f"{config.api_url}/file/bot{{token}}{environment}/{{path}}",
                )
            ),
        )

        yield bot

        await bot.session.close()

    @provide(
        scope=Scope.APP,
        provides=AnyOf[RichLimitReader, RichMediaUploader, RichSender, RichReplier],
    )
    def get_rich_messenger(
        self, *, bot: Bot, client: Client, config: InlineBotConfig
    ) -> InlineBotRichMessenger:
        return InlineBotRichMessenger(bot=bot, client=client, local_mode=config.local_mode)

    @provide(scope=Scope.REQUEST)
    def get_bot_file_repository(self, *, session: AsyncSession, bot: Bot) -> BotFileRepository:
        return SQLBotFileRepository(session=session, bot_id=bot.id)
