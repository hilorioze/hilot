import asyncio

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all
from pyrogram import Client

from hilot.application.media.deliver import DeliverMedia
from hilot.application.media.request_download import RequestDownload
from hilot.domain.value_objects.message import AccountId
from hilot.infrastructure.queue.routes import Route, get_delivery_route
from hilot.infrastructure.telegram.authorization import Authorization
from hilot.presentation.taskiq.media import deliver_media

from .config.database import DatabaseConfig
from .config.loader import load_config
from .config.nats import NatsConfig
from .config.s3 import S3Config
from .config.schemas import BotSchema
from .config.telegram import TelegramConfig
from .config.worker import BotConfig
from .di.database import DatabaseProvider
from .di.extractors import LinkMatcherProvider
from .di.formatters import FormatterProvider
from .di.handlers import HandlerProvider
from .di.media import WorkspaceProvider
from .di.queue import QueueProvider
from .di.s3 import S3Provider, StoredFileProvider
from .di.telegram import SessionProvider, TelegramProvider
from .worker import configure_logging, run_worker


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(RequestDownload, DeliverMedia)


async def run() -> None:
    schema: BotSchema = load_config(schema=BotSchema, secrets_scope="bot")
    authorization: Authorization = Authorization.parse(schema.session_string.get_secret_value())

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
        WorkspaceProvider(),
        _InteractorProvider(),
        context={
            DatabaseConfig: schema.database,
            S3Config: schema.s3,
            NatsConfig: schema.nats,
            # the file ids of the uploads belong to the account, so only its bot delivers them
            Route: get_delivery_route(AccountId(authorization.user_id)),
            Authorization: authorization,
            TelegramConfig: schema.telegram,
            BotConfig: schema.bot,
        },
    )

    client: Client = await container.get(Client)

    async with client:
        await run_worker(container=container, config=schema.bot, task=deliver_media)

    await container.close()


def main() -> None:
    configure_logging()

    asyncio.run(run())


if __name__ == "__main__":
    main()
