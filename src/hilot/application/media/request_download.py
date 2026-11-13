from dataclasses import dataclass

from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.messenger import ProgressIndicator, UploadLimitReader
from hilot.domain.value_objects.download import DownloadRequest
from hilot.domain.value_objects.message import Link, SourceMessage


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestDownloadDTO:
    source: SourceMessage
    links: list[Link]


class RequestDownload:
    def __init__(
        self,
        *,
        link_matcher: LinkMatcher,
        progress_indicator: ProgressIndicator,
        upload_limit_reader: UploadLimitReader,
        download_scheduler: DownloadScheduler,
    ) -> None:
        self._link_matcher: LinkMatcher = link_matcher
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._upload_limit_reader: UploadLimitReader = upload_limit_reader
        self._download_scheduler: DownloadScheduler = download_scheduler

    async def __call__(self, data: RequestDownloadDTO) -> None:
        links: list[Link] = [
            link
            for link in data.links
            if not link.has_video_preview and self._link_matcher.matches(link.url)
        ]

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
