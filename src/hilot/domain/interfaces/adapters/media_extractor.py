from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Protocol

from hilot.domain.value_objects.cookie import Cookie
from hilot.domain.value_objects.media import ExtractedMedia


class Extraction(Protocol):
    @property
    def entries(self) -> list[ExtractedMedia]: ...

    @property
    def cookies(self) -> list[Cookie]: ...

    def download(self, entry: ExtractedMedia) -> AbstractAsyncContextManager[Path]: ...


class MediaExtractor(Protocol):
    def extract(
        self, *, url: str, cookies: list[Cookie], directory: Path, size_limit: int
    ) -> AbstractAsyncContextManager[Extraction]: ...
