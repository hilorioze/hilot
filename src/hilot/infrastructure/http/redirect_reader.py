import ipaddress
from typing import override
from urllib.parse import urljoin, urlsplit

from aiohttp import ClientError, ClientSession

from hilot.domain.interfaces.adapters.redirect_reader import RedirectReader

_REDIRECT_STATUSES: set[int] = {301, 302, 303, 307, 308}


class HttpRedirectReader(RedirectReader):
    def __init__(self, *, session: ClientSession) -> None:
        self._session: ClientSession = session

    @override
    async def read_redirect(self, url: str) -> str | None:
        # aiohttp connects to an ip address in a link without asking the resolver
        if _is_private_address(urlsplit(url).hostname or ""):
            return None

        try:
            async with self._session.get(url, allow_redirects=False) as response:
                location: str | None = response.headers.get("Location")
        # any link of a message gets here, a dead one or not http at all too
        except ClientError, TimeoutError:
            return None

        if response.status not in _REDIRECT_STATUSES or location is None:
            return None

        return urljoin(url, location)


def _is_private_address(host: str) -> bool:
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False
