from dataclasses import replace

from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.redirect_reader import RedirectReader
from hilot.domain.value_objects.message import Link

# a share link leads to the link of its post through a couple of redirects
_MAX_REDIRECTS: int = 5


# the links some extractor takes, a share link as the link of its post
class SupportedLinkFinder:
    def __init__(self, *, link_matcher: LinkMatcher, redirect_reader: RedirectReader) -> None:
        self._link_matcher: LinkMatcher = link_matcher
        self._redirect_reader: RedirectReader = redirect_reader

    async def find_supported_links(self, links: list[Link]) -> list[Link]:
        supported_links: list[Link] = []

        for link in links:
            url: str | None = await self._find_supported_url(link.url)

            if url is not None:
                supported_links.append(replace(link, url=url))

        return supported_links

    async def _find_supported_url(self, url: str) -> str | None:
        for _ in range(_MAX_REDIRECTS):
            if self._link_matcher.matches(url):
                return url

            location: str | None = await self._redirect_reader.read_redirect(url)

            if location is None:
                return None

            url = location

        return None
