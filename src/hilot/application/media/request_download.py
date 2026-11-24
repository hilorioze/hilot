from dataclasses import dataclass, replace

from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.link_matcher import LinkMatcher
from hilot.domain.interfaces.adapters.messenger import (
    ProgressIndicator,
    TextEditor,
    TextSender,
    UploadLimitReader,
)
from hilot.domain.interfaces.adapters.redirect_reader import RedirectReader
from hilot.domain.value_objects.download import DownloadRequest, DownloadTrigger
from hilot.domain.value_objects.message import Link, MessageId, SourceMessage

# a share link leads to the link of its post through a couple of redirects
_MAX_REDIRECTS: int = 5


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestDownloadDTO:
    source: SourceMessage
    trigger: DownloadTrigger

    links: list[Link]
    reply_to: MessageId


class RequestDownload:
    def __init__(
        self,
        *,
        link_matcher: LinkMatcher,
        redirect_reader: RedirectReader,
        progress_indicator: ProgressIndicator,
        text_editor: TextEditor,
        text_sender: TextSender,
        failure_formatter: FailureFormatter,
        upload_limit_reader: UploadLimitReader,
        download_scheduler: DownloadScheduler,
    ) -> None:
        self._link_matcher: LinkMatcher = link_matcher
        self._redirect_reader: RedirectReader = redirect_reader
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._text_editor: TextEditor = text_editor
        self._text_sender: TextSender = text_sender
        self._failure_formatter: FailureFormatter = failure_formatter
        self._upload_limit_reader: UploadLimitReader = upload_limit_reader
        self._download_scheduler: DownloadScheduler = download_scheduler

    async def __call__(self, data: RequestDownloadDTO) -> None:
        links: list[Link] = []

        for link in data.links:
            # the preview plays the video by itself, unless the file is asked for
            if link.has_video_preview and data.trigger == DownloadTrigger.LINK:
                continue

            url: str | None = await self._find_supported_url(link.url)

            if url is not None:
                links.append(replace(link, url=url))

        request: DownloadRequest = DownloadRequest(
            source=data.source,
            trigger=data.trigger,
            links=links,
            reply_to=data.reply_to,
            size_limit=self._upload_limit_reader.get_upload_limit(),
        )

        # a message without supported links is left alone, a command says so
        if not links:
            if request.is_commanded():
                await self._report_no_links(request)

            return

        if request.shows_progress():
            await self._progress_indicator.show_progress(data.source)

        await self._download_scheduler.schedule_download(request)

    async def _report_no_links(self, request: DownloadRequest) -> None:
        text: str = self._failure_formatter.format_no_links()

        # a command with links of its own keeps them in sight
        if request.replaces_command():
            await self._text_editor.edit_text(source=request.source, text=text)
        else:
            await self._text_sender.send_text(source=request.source, part=0, text=text, quote=None)

    async def _find_supported_url(self, url: str) -> str | None:
        for _ in range(_MAX_REDIRECTS):
            if self._link_matcher.matches(url):
                return url

            location: str | None = await self._redirect_reader.read_redirect(url)

            if location is None:
                return None

            url = location

        return None
