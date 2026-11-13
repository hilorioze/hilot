import asyncio
import sys
from pathlib import Path

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from pyrogram import Client
from pyrogram.storage.sqlite_storage import SQLiteStorage
from pyrogram.storage.storage import Storage

from .config.loader import load_config
from .config.schemas import LoginSchema
from .config.telegram import TelegramConfig
from .di.telegram import TelegramProvider


class _StorageProvider(Provider):
    @provide(scope=Scope.APP)
    def get_storage(self) -> Storage:
        # the new session stays in memory until its string is printed
        return SQLiteStorage("hilot", workdir=Path.cwd(), in_memory=True)


async def run() -> None:
    schema: LoginSchema = load_config(schema=LoginSchema)

    container: AsyncContainer = make_async_container(
        TelegramProvider(), _StorageProvider(), context={TelegramConfig: schema.telegram}
    )
    client: Client = await container.get(Client)

    # telegram wants a recaptcha token from the android sdk to send a login code to the android app, a qr code scanned by a logged in device needs none
    # the test backend shouldn't have it
    await client.start(use_qr=not schema.telegram.test_mode)

    sys.stdout.write(f"{await client.export_session_string()}\n")

    await client.stop()
    await container.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
