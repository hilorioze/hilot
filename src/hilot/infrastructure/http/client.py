import ipaddress
import socket
from typing import override

from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.resolver import DefaultResolver
from yt_dlp.utils.networking import std_headers


# a link from any chat must not reach the hosts of the private networks, the tailnet included
class _PublicResolver(AbstractResolver):
    def __init__(self) -> None:
        self._resolver: AbstractResolver = DefaultResolver()

    @override
    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        results: list[ResolveResult] = await self._resolver.resolve(host, port, family)
        public_results: list[ResolveResult] = [
            result for result in results if ipaddress.ip_address(result["host"]).is_global
        ]

        if not public_results:
            raise OSError

        return public_results

    @override
    async def close(self) -> None:
        await self._resolver.close()


def create_http_session() -> ClientSession:
    return ClientSession(
        connector=TCPConnector(resolver=_PublicResolver()),
        # the headers of yt-dlp, which downloads the link afterwards; facebook answers a request without `Sec-Fetch-Mode` with 400
        headers=dict(std_headers),
        # a message waits for its links, so a slow site gives up early
        timeout=ClientTimeout(total=10),
    )
