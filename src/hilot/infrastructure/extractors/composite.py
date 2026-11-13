from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import override

from hilot.domain.errors.extraction import NoMediaError, UnsupportedLinkError
from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.media_extractor import Extraction, MediaExtractor
from hilot.domain.value_objects.cookie import Cookie


class AnyLinkMatcher(LinkMatcher):
    def __init__(self, *, matchers: list[LinkMatcher]) -> None:
        self._matchers: list[LinkMatcher] = matchers

    @override
    def matches(self, url: str) -> bool:
        return any(matcher.matches(url) for matcher in self._matchers)


# the extractors take a link in turn until one finds media in it, and the last one reports why none did
class FallbackMediaExtractor(MediaExtractor):
    def __init__(self, *, extractors: list[MediaExtractor]) -> None:
        self._extractors: list[MediaExtractor] = extractors

    @override
    @asynccontextmanager
    async def extract(
        self, *, url: str, cookies: list[Cookie], directory: Path, size_limit: int
    ) -> AsyncGenerator[Extraction]:
        async with AsyncExitStack() as stack:
            yield await self._enter_extraction(
                stack=stack, url=url, cookies=cookies, directory=directory, size_limit=size_limit
            )

    async def _enter_extraction(
        self,
        *,
        stack: AsyncExitStack,
        url: str,
        cookies: list[Cookie],
        directory: Path,
        size_limit: int,
    ) -> Extraction:
        # only the errors of entering an extraction move on to the next extractor, the ones of its use belong to it
        for media_extractor in self._extractors[:-1]:
            try:
                return await stack.enter_async_context(
                    media_extractor.extract(
                        url=url, cookies=cookies, directory=directory, size_limit=size_limit
                    )
                )
            except UnsupportedLinkError, NoMediaError:
                pass

        return await stack.enter_async_context(
            self._extractors[-1].extract(
                url=url, cookies=cookies, directory=directory, size_limit=size_limit
            )
        )
