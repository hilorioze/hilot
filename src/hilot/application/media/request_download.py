from dataclasses import dataclass, replace

from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.messenger import ProgressIndicator, UploadLimitReader
from hilot.domain.interfaces.adapters.redirect_reader import RedirectReader
from hilot.domain.value_objects.download import DownloadRequest
from hilot.domain.value_objects.message import Link, SourceMessage

# a share link leads to the link of its post through a couple of redirects
_MAX_REDIRECTS: int = 5


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestDownloadDTO:
    source: SourceMessage
    links: list[Link]


class RequestDownload:
    def __init__(
        self,
        *,
        link_matcher: LinkMatcher,
        redirect_reader: RedirectReader,
        progress_indicator: ProgressIndicator,
        upload_limit_reader: UploadLimitReader,
        download_scheduler: DownloadScheduler,
    ) -> None:
        self._link_matcher: LinkMatcher = link_matcher
        self._redirect_reader: RedirectReader = redirect_reader
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._upload_limit_reader: UploadLimitReader = upload_limit_reader
        self._download_scheduler: DownloadScheduler = download_scheduler

    async def __call__(self, data: RequestDownloadDTO) -> None:
        links: list[Link] = []

        for link in data.links:
            if link.has_video_preview:
                continue

            url: str | None = await self._find_supported_url(link.url)

            if url is not None:
                links.append(replace(link, url=url))

        if not links:
            return

        if data.source.shows_progress():
            await self._progress_indicator.show_progress(data.source)

        request: DownloadRequest = DownloadRequest(
            source=data.source,
            links=links,
            size_limit=self._upload_limit_reader.get_upload_limit(),
        )
        await self._download_scheduler.schedule_download(request)

    async def _find_supported_url(self, url: str) -> str | None:
        for _ in range(_MAX_REDIRECTS):
            if self._link_matcher.matches(url):
                return url

            location: str | None = await self._redirect_reader.read_redirect(url)

            if location is None:
                return None

            url = location

        return None
