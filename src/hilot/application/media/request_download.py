from dataclasses import dataclass

from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    ProgressIndicator,
    UploadLimitReader,
)
from hilot.domain.value_objects.download import (
    DownloadPurpose,
    DownloadRequest,
    DownloadTrigger,
)
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    Link,
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
        progress_indicator: ProgressIndicator,
        command_answerer: CommandAnswerer,
        failure_formatter: FailureFormatter,
        upload_limit_reader: UploadLimitReader,
        download_scheduler: DownloadScheduler,
    ) -> None:
        self._link_finder: SupportedLinkFinder = link_finder
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._command_answerer: CommandAnswerer = command_answerer
        self._failure_formatter: FailureFormatter = failure_formatter
        self._upload_limit_reader: UploadLimitReader = upload_limit_reader
        self._download_scheduler: DownloadScheduler = download_scheduler

    async def __call__(self, data: RequestDownloadDTO) -> None:
        links: list[Link] = await self._link_finder.find_supported_links(data.links)

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
