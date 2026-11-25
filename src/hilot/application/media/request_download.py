from dataclasses import dataclass
from datetime import UTC, datetime

from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    LinkPreviewReader,
    ProgressIndicator,
    UploadLimitReader,
)
from hilot.domain.interfaces.adapters.preview_wait_scheduler import PreviewWaitScheduler
from hilot.domain.value_objects.download import (
    LINK_PREVIEW_TIMEOUT,
    DownloadPurpose,
    DownloadRequest,
    DownloadTrigger,
    PreviewWait,
)
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    Link,
    LinkPreview,
    MessageId,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText

from .links import SupportedLinkFinder


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
        link_finder: SupportedLinkFinder,
        link_preview_reader: LinkPreviewReader,
        preview_wait_scheduler: PreviewWaitScheduler,
        progress_indicator: ProgressIndicator,
        command_answerer: CommandAnswerer,
        failure_formatter: FailureFormatter,
        upload_limit_reader: UploadLimitReader,
        download_scheduler: DownloadScheduler,
    ) -> None:
        self._link_finder: SupportedLinkFinder = link_finder
        self._link_preview_reader: LinkPreviewReader = link_preview_reader
        self._preview_wait_scheduler: PreviewWaitScheduler = preview_wait_scheduler
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._command_answerer: CommandAnswerer = command_answerer
        self._failure_formatter: FailureFormatter = failure_formatter
        self._upload_limit_reader: UploadLimitReader = upload_limit_reader
        self._download_scheduler: DownloadScheduler = download_scheduler

    async def __call__(self, data: RequestDownloadDTO) -> None:
        preview: LinkPreview | None = (
            await self._link_preview_reader.read_link_preview(data.source)
            if data.trigger == DownloadTrigger.LINK and data.links
            else None
        )

        # the links of a message wait for the preview telegram still builds, until the timeout after the message
        if (
            preview is not None
            and preview.is_pending
            and datetime.now(UTC) < data.source.sent_at + LINK_PREVIEW_TIMEOUT
        ):
            await self._preview_wait_scheduler.schedule_preview_wait(
                PreviewWait(source=data.source, links=data.links)
            )

            return

        links: list[Link] = await self._link_finder.find_supported_links(
            [
                link
                for link in data.links
                if not await self._plays_in_preview(link=link, preview=preview)
            ]
        )

        request: DownloadRequest = DownloadRequest(
            source=data.source,
            trigger=data.trigger,
            purpose=DownloadPurpose.DELIVERY,
            links=links,
            reply_to=data.reply_to,
            size_limit=self._upload_limit_reader.get_upload_limit(),
        )

        # a message without supported links is left alone, a command says so
        if not links:
            if request.is_commanded():
                await self._command_answerer.answer_command(
                    source=request.source,
                    answer=CommandAnswer(
                        entries=[
                            AnswerEntry(
                                kind=AnswerKind.ERROR,
                                text=RichText.plain(self._failure_formatter.format_no_links()),
                            )
                        ]
                    ),
                )

            return

        if request.shows_progress():
            await self._progress_indicator.show_progress(data.source)

        await self._download_scheduler.schedule_download(request)

    # the preview plays the video by itself, unless the file is asked for
    async def _plays_in_preview(self, *, link: Link, preview: LinkPreview | None) -> bool:
        if preview is None or not preview.plays_video or preview.url is None:
            return False

        # telegram keeps the preview under its own form of the link: without `www.`, with sorted parameters and no tracking ones
        return await self._link_preview_reader.read_preview_url(link.url) == preview.url
