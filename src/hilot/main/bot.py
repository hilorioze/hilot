import asyncio
from zoneinfo import ZoneInfo

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all
from pyrogram import Client

from hilot.application.check_ins.check_in import RunCheckIn
from hilot.application.media.deliver import DeliverMedia
from hilot.application.media.request_download import RequestDownload
from hilot.application.watermarks.reply import ReplyWatermarkCheck
from hilot.application.watermarks.request_check import RequestWatermarkCheck
from hilot.domain.value_objects.check_in import CheckIn
from hilot.domain.value_objects.message import AccountId
from hilot.infrastructure.queue.routes import Route, get_delivery_route, get_watermark_reply_route
from hilot.infrastructure.telegram.authorization import Authorization
from hilot.presentation.schedule.check_ins import run_check_ins
from hilot.presentation.taskiq.media import deliver_media
from hilot.presentation.taskiq.watermarks import reply_watermark_check

from .config.database import DatabaseConfig
from .config.loader import load_config
from .config.nats import NATSConfig
from .config.s3 import S3Config
from .config.schemas import BotSchema
from .config.telegram import TelegramConfig
from .config.worker import BotConfig
from .di.database import DatabaseProvider
from .di.extractors import LinkMatcherProvider
from .di.formatters import FormatterProvider
from .di.handlers import HandlerProvider
from .di.http import RedirectReaderProvider
from .di.media import WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider, StoredFileProvider
from .di.telegram import SessionProvider, TelegramProvider
from .di.watermarks import DetectableMediaMatcherProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(
        RequestDownload, DeliverMedia, RequestWatermarkCheck, ReplyWatermarkCheck, RunCheckIn
    )


async def run() -> None:
    schema: BotSchema = load_config(schema=BotSchema, secrets_scope="bot")
    authorization: Authorization = Authorization.parse(schema.session_string.get_secret_value())
    account_id: AccountId = AccountId(authorization.user_id)

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        S3Provider(),
        StoredFileProvider(),
        QueueProvider(),
        SessionProvider(),
        TelegramProvider(),
        HandlerProvider(),
        FormatterProvider(),
        LinkMatcherProvider(),
        RedirectReaderProvider(),
        DetectableMediaMatcherProvider(),
        WorkspaceProvider(),
        _InteractorProvider(),
        context={
            DatabaseConfig: schema.database,
            S3Config: schema.s3,
            NATSConfig: schema.nats,
            # the file ids of the uploads belong to the account, so only its bot delivers them
            Route: get_delivery_route(account_id),
            Authorization: authorization,
            TelegramConfig: schema.telegram,
            BotConfig: schema.bot,
        },
    )

    client: Client = await container.get(Client)

    async with client, asyncio.TaskGroup() as group:
        check_in_tasks: list[asyncio.Task[None]] = [
            group.create_task(
                run_check_ins(
                    container=container,
                    check_in=CheckIn(
                        bot=config.bot, command=config.command, buttons=config.buttons
                    ),
                    start=config.start,
                    end=config.end,
                    timezone=ZoneInfo(schema.telegram.timezone),
                )
            )
            for config in schema.bot.check_ins
        ]

        await run_worker(
            container=container,
            config=schema.bot,
            tasks={
                get_delivery_route(account_id): deliver_media,
                get_watermark_reply_route(account_id): reply_watermark_check,
            },
        )

        # the check-ins never finish; stop them with the worker
        for task in check_in_tasks:
            task.cancel()

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
