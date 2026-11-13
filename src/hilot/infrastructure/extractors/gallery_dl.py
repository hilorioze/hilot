import asyncio
import os
import threading
from collections.abc import AsyncGenerator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, override

from gallery_dl import config, extractor, formatter
from gallery_dl.exception import AuthorizationError, ExtractionError, StopDownload
from gallery_dl.extractor.common import Extractor
from gallery_dl.job import DownloadJob
from gallery_dl.output import NullOutput
from requests.cookies import RequestsCookieJar

from hilot.domain.errors.extraction import (
    LoginRequiredError,
    MediaUnavailableError,
    NoMediaError,
    TooBigError,
    UnsupportedLinkError,
)
from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.media_extractor import Extraction, MediaExtractor
from hilot.domain.value_objects.cookie import Cookie
from hilot.domain.value_objects.media import ExtractedMedia, MediaKey
from hilot.infrastructure.metrics import LOGIN_REQUIRED

from .cookies import fill_cookie_jar, read_cookie_jar


class GalleryDlLinkMatcher(LinkMatcher):
    @override
    def matches(self, url: str) -> bool:
        return _find_extractor(url) is not None


class GalleryDlMediaExtractor(MediaExtractor):
    def __init__(self, *, proxy: str | None) -> None:
        # gallery-dl takes its options only from the global config
        config.set(("extractor",), "proxy", proxy)
        # gallery-dl caches logins and tokens, so they stay in memory like the cookies
        config.set(("cache",), "file", ":memory:")
        # a download reports every chunk, so the size limit stops it right away
        config.set(("downloader",), "progress", 0.0)

    @override
    @asynccontextmanager
    async def extract(
        self, *, url: str, cookies: list[Cookie], directory: Path, size_limit: int
    ) -> AsyncGenerator[_GalleryDlExtraction]:
        root: Extractor | None = _find_extractor(url)

        if root is None:
            raise UnsupportedLinkError

        # the files go to the workspace instead of `./gallery-dl/`, and the children get it from their parent
        root._parentdir = f"{directory}{os.sep}"  # noqa: SLF001

        job: _GalleryDlJob = _GalleryDlJob(root)
        fill_cookie_jar(jar=job.cookies, cookies=cookies)

        status: int = await asyncio.to_thread(job.run)

        # a partly failed extraction still has the files it found
        if not job.files:
            raise _translate_status(status=status, errors=job.errors, root=root)

        yield _GalleryDlExtraction(job=job, size_limit=size_limit)


class _GalleryDlExtraction(Extraction):
    def __init__(self, *, job: _GalleryDlJob, size_limit: int) -> None:
        self._cookies: RequestsCookieJar = job.cookies
        self._files: dict[ExtractedMedia, _GalleryDlFile] = {
            self._create_entry(file): file for file in job.files
        }
        self._progress: _DownloadProgress = _DownloadProgress(size_limit=size_limit)

    @property
    @override
    def entries(self) -> list[ExtractedMedia]:
        return list(self._files)

    @property
    @override
    def cookies(self) -> list[Cookie]:
        return read_cookie_jar(self._cookies)

    @override
    @asynccontextmanager
    async def download(self, entry: ExtractedMedia) -> AsyncGenerator[Path]:
        file: _GalleryDlFile = self._files[entry]

        try:
            path: Path = await asyncio.to_thread(
                file.job.download_file, file=file, progress=self._progress
            )
        except asyncio.CancelledError:
            # a thread can't be cancelled, so the progress stops the download
            self._progress.cancelled.set()
            raise

        try:
            yield path
        finally:
            await asyncio.to_thread(path.unlink)

    @classmethod
    def _create_entry(cls, file: _GalleryDlFile) -> ExtractedMedia:
        # gallery-dl titles a tiktok track after its post, the track's own title and author are in `music`
        track: dict[str, Any] = (
            file.kwdict.get("music", {}) if file.kwdict.get("type") == "audio" else {}
        )

        return ExtractedMedia(
            media_key=MediaKey(
                extractor=file.job.extractor.category, media_id=cls._get_media_id(file)
            ),
            # gallery-dl knows the size only once the download starts
            size=None,
            title=track.get("title") or file.kwdict.get("title"),
            performer=track.get("authorName"),
        )

    @staticmethod
    def _get_media_id(file: _GalleryDlFile) -> str:
        archive_fmt: str = file.job.extractor.archive_fmt

        # some extractors have no archive id, their file links tell the files apart
        if not archive_fmt:
            return file.url

        return formatter.parse(archive_fmt).format_map(file.kwdict)


# a job collects the files of its extractor first, so the bot downloads them one by one later
class _GalleryDlJob(DownloadJob):
    _LINK_SCHEMES: ClassVar[tuple[str, ...]] = ("http:", "https:")

    # gallery-dl creates the children with the same arguments
    def __init__(self, extr: Extractor, parent: _GalleryDlJob | None = None) -> None:
        super().__init__(extr, parent)

        self.files: list[_GalleryDlFile] = [] if parent is None else parent.files
        self.cookies: RequestsCookieJar = RequestsCookieJar() if parent is None else parent.cookies
        self.errors: list[ExtractionError] = [] if parent is None else parent.errors

        # gallery-dl loads the cookies right before an extractor sets its own, and only for the sites using them
        extr._init_cookies = self._use_cookies  # noqa: SLF001

    @override
    def dispatch(self, messages: Iterable[tuple[int, str, dict[str, Any]]]) -> int | None:
        try:
            return super().dispatch(messages)
        except ExtractionError as error:
            # gallery-dl logs the errors of an extraction and keeps only their codes in the job status
            self.errors.append(error)

            raise

    @override
    def handle_directory(self, kwdict: dict[str, Any]) -> None:
        # a download sets the directory of its file itself
        pass

    @override
    def handle_url(self, url: str, kwdict: dict[str, Any]) -> None:
        links: list[str] = [
            link
            # gallery-dl hands some videos to yt-dlp as `ytdl:` links, which would ignore the size limit; take their direct links from `_fallback`
            for link in (url, *kwdict.get("_fallback", ()))
            # a `text:` link holds only the text of a post
            if link.startswith(self._LINK_SCHEMES)
        ]

        if links:
            self.files.append(
                _GalleryDlFile(job=self, url=links[0], kwdict={**kwdict, "_fallback": links[1:]})
            )

    @override
    def _build_extractor_filter(self) -> Callable[[Extractor], bool]:
        is_configured: Callable[[Extractor], bool] = super()._build_extractor_filter()

        # a post can link to a file on any host too
        return lambda child: is_configured(child) and _is_allowed(child)

    def download_file(self, *, file: _GalleryDlFile, progress: _DownloadProgress) -> Path:
        # gallery-dl gives the output of a job to its downloaders on the first download
        self.out = progress
        # the collection has already reported its status
        self.status = 0

        super().handle_directory(file.kwdict)
        super().handle_url(file.url, file.kwdict)

        if self.status:
            raise MediaUnavailableError

        return Path(self.pathfmt.realpath)

    def _use_cookies(self) -> None:
        self.extractor.cookies = self.extractor.session.cookies = self.cookies


@dataclass(frozen=True, slots=True, kw_only=True)
class _GalleryDlFile:
    job: _GalleryDlJob
    url: str
    kwdict: dict[str, Any]


class _DownloadProgress(NullOutput):
    def __init__(self, *, size_limit: int) -> None:
        self._size_limit: int = size_limit
        self.cancelled: threading.Event = threading.Event()

    @override
    def progress(
        self, bytes_total: int | None, bytes_downloaded: int, bytes_per_second: int
    ) -> None:
        if self.cancelled.is_set():
            raise StopDownload

        # the total is the size the server announces
        if bytes_total is not None and bytes_total > self._size_limit:
            raise TooBigError(size=bytes_total)

        if bytes_downloaded > self._size_limit:
            raise TooBigError(size=None)


def _find_extractor(url: str) -> Extractor | None:
    found: Extractor | None = extractor.find(url)

    if found is None or not _is_allowed(found):
        return None

    return found


# a direct link would take a file from any host, the internal ones too
def _is_allowed(found: Extractor) -> bool:
    return found.category != "directlink"


def _translate_status(*, status: int, errors: list[ExtractionError], root: Extractor) -> Exception:
    if not status:
        return NoMediaError()

    # gallery-dl has no own error for a redirect to the login page, only its message, and a failed login shares the code of a missing one
    if any(
        error.code == AuthorizationError.code or "redirect to login page" in str(error)
        for error in errors
    ):
        LOGIN_REQUIRED.labels(extractor=root.category).inc()

        return LoginRequiredError()

    return MediaUnavailableError()
