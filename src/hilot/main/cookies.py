import asyncio
from argparse import ArgumentParser, Namespace
from http.cookiejar import MozillaCookieJar
from pathlib import Path

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide_all

from hilot.application.cookies.import_ import ImportCookies, ImportCookiesDTO
from hilot.domain.value_objects.cookie import CookieSource
from hilot.infrastructure.extractors.cookies import read_cookie_jar

from .config.database import DatabaseConfig
from .config.encryption import EncryptionConfig
from .config.loader import load_config
from .config.schemas import CookieImportSchema
from .di.cookies import CookiesProvider
from .di.database import DatabaseProvider
from .di.encryption import EncryptionProvider


class _InteractorProvider(Provider):
    scope = Scope.REQUEST

    interactors = provide_all(ImportCookies)


async def run(*, path: Path, source: CookieSource) -> None:
    schema: CookieImportSchema = load_config(schema=CookieImportSchema, secrets_scope="cookies")

    jar: MozillaCookieJar = MozillaCookieJar(path)
    # the session cookies of a login count as much as the lasting ones
    jar.load(ignore_discard=True)

    container: AsyncContainer = make_async_container(
        DatabaseProvider(),
        EncryptionProvider(),
        CookiesProvider(),
        _InteractorProvider(),
        context={DatabaseConfig: schema.database, EncryptionConfig: schema.encryption},
    )

    async with container() as request_container:
        interactor: ImportCookies = await request_container.get(ImportCookies)

        await interactor(ImportCookiesDTO(cookies=read_cookie_jar(jar), source=source))

    await container.close()


def main() -> None:
    parser: ArgumentParser = ArgumentParser(
        prog="hilot-cookies",
        description="replace the stored cookies of the sites in a cookies.txt with its ones",
    )
    parser.add_argument("path", type=Path, help="cookies.txt exported from a logged in browser")
    parser.add_argument(
        "--whole-browser",
        action="store_true",
        help="the cookies.txt holds every cookie of the browser, so the stored cookies of the sites missing from it are deleted too",
    )

    options: Namespace = parser.parse_args()

    asyncio.run(
        run(
            path=options.path,
            source=CookieSource.BROWSER if options.whole_browser else CookieSource.SITES,
        )
    )


if __name__ == "__main__":
    main()
