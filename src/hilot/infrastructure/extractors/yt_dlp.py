import asyncio
import logging
import threading
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, cast, override

from yt_dlp.extractor import gen_extractor_classes
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import DownloadCancelled, DownloadError, ExtractorError, UnsupportedError
from yt_dlp.utils import GeoRestrictedError as YtDlpGeoRestrictedError
from yt_dlp.YoutubeDL import YoutubeDL

from hilot.domain.errors.extraction import (
    GeoRestrictedError,
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

# the generic extractor takes any page, and the disabled ones only hand over to it
_EXTRACTORS: list[type[InfoExtractor]] = [
    extractor
    for extractor in gen_extractor_classes()
    if extractor._ENABLED and extractor.IE_NAME != "generic"  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue]
]


class YtDlpLinkMatcher(LinkMatcher):
    @override
    def matches(self, url: str) -> bool:
        return _is_supported(url)


class YtDlpMediaExtractor(MediaExtractor):
    def __init__(self, *, proxy: str | None, video_required: bool) -> None:
        self._proxy: str | None = proxy
        self._video_required: bool = video_required

    @override
    @asynccontextmanager
    async def extract(
        self, *, url: str, cookies: list[Cookie], directory: Path, size_limit: int
    ) -> AsyncGenerator[_YtDlpExtraction]:
        if not _is_supported(url):
            raise UnsupportedLinkError

        with YoutubeDL(
            {
                # yt-dlp calls only `debug`, `warning` and `error` of its logger, the stubs want a whole class of its own
                "logger": cast(Any, logging.getLogger("yt_dlp")),
                "noprogress": True,
                "proxy": self._proxy,
                "noplaylist": True,
                # the best formats under the limit, or the best ones to report them as too big
                "format": f"(bv*+ba/b)[filesize<?{size_limit}][filesize_approx<?{size_limit}]/bv*+ba/b",
                # what telegram plays without transcoding
                "format_sort": ["vcodec:h264", "acodec:aac", "ext:mp4:m4a"],
                "paths": {"home": str(directory)},
                # a long description as the title would overflow the file name limit of 255 bytes
                "outtmpl": "%(title).150B [%(id)s].%(ext)s",
            },
            auto_init=False,
        ) as ydl:
            # yt-dlp creates an extractor only for a link it handles, the stubs take only the created ones
            for extractor in _EXTRACTORS:
                ydl.add_info_extractor(extractor)  # pyright: ignore[reportArgumentType]

            fill_cookie_jar(jar=ydl.cookiejar, cookies=cookies)

            with _translate_errors():
                # the stubs type the info without the fields yt-dlp adds to it
                info: dict[str, Any] = cast(
                    dict[str, Any], await asyncio.to_thread(ydl.extract_info, url, download=False)
                )

            infos: list[dict[str, Any]] = self._list_infos(info)

            # yt-dlp gets a tiktok photo post only as its track, so an extraction without a video can be left to another extractor
            # a format of an unknown codec, like facebook's progressive ones, has no `vcodec` at all
            if self._video_required and all(info.get("vcodec") == "none" for info in infos):
                raise NoMediaError

            yield _YtDlpExtraction(ydl=ydl, infos=infos, size_limit=size_limit)

    @classmethod
    def _list_infos(cls, info: dict[str, Any]) -> list[dict[str, Any]]:
        if info.get("_type") != "playlist":
            return [info]

        # a playlist lists the videos or other playlists
        return [video for entry in info["entries"] for video in cls._list_infos(entry)]


class _YtDlpExtraction(Extraction):
    def __init__(self, *, ydl: YoutubeDL, infos: list[dict[str, Any]], size_limit: int) -> None:
        self._ydl: YoutubeDL = ydl
        self._infos: dict[ExtractedMedia, dict[str, Any]] = {
            self._create_entry(info): info for info in infos
        }
        self._size_limit: int = size_limit
        self._cancelled: threading.Event = threading.Event()

        ydl.add_progress_hook(self._check_progress)

    @property
    @override
    def entries(self) -> list[ExtractedMedia]:
        return list(self._infos)

    @property
    @override
    def cookies(self) -> list[Cookie]:
        return read_cookie_jar(self._ydl.cookiejar)

    @override
    @asynccontextmanager
    async def download(self, entry: ExtractedMedia) -> AsyncGenerator[Path]:
        try:
            with _translate_errors():
                info: dict[str, Any] = cast(
                    dict[str, Any],
                    await asyncio.to_thread(
                        # the info keeps the formats, so yt-dlp selects them again and downloads them
                        self._ydl.process_ie_result,
                        self._infos[entry],  # pyright: ignore[reportArgumentType]
                        download=True,
                    ),
                )
        except asyncio.CancelledError:
            # a thread can't be cancelled, so the progress hook stops the download
            self._cancelled.set()
            raise

        path: Path = Path(info["requested_downloads"][0]["filepath"])

        try:
            yield path
        finally:
            await asyncio.to_thread(path.unlink)

    def _check_progress(self, progress: dict[str, Any]) -> None:
        if self._cancelled.is_set():
            raise DownloadCancelled

        # the size of a format is often unknown or only estimated beforehand
        if progress.get("downloaded_bytes", 0) > self._size_limit:
            raise TooBigError(size=None)

    @staticmethod
    def _create_entry(info: dict[str, Any]) -> ExtractedMedia:
        return ExtractedMedia(
            media_key=MediaKey(extractor=info["extractor_key"], media_id=info["id"]),
            # the info of a merged format has only an estimated size
            size=info.get("filesize") or info.get("filesize_approx"),
            title=info.get("track") or info.get("title"),
            performer=info.get("artist") or info.get("uploader"),
        )


def _is_supported(url: str) -> bool:
    return any(extractor.suitable(url) for extractor in _EXTRACTORS)


@contextmanager
def _translate_errors() -> Generator[None]:
    try:
        yield
    except DownloadError as error:
        # yt-dlp reports its errors as a `DownloadError` with the original error inside
        raise _translate_error(error.exc_info[1]) from error


def _translate_error(error: BaseException | None) -> Exception:
    match error:
        # a short link to a page no extractor takes gives a `DownloadError` without an exception
        case None | UnsupportedError():
            return UnsupportedLinkError()
        case YtDlpGeoRestrictedError():
            return GeoRestrictedError()
        # yt-dlp has no own errors for a missing login or media, only their messages
        case ExtractorError() if error.orig_msg.startswith("No video formats found"):
            return NoMediaError()
        case ExtractorError() if "--cookies" in error.orig_msg:
            LOGIN_REQUIRED.labels(extractor=error.ie).inc()

            return LoginRequiredError()
        case _:
            return MediaUnavailableError()
