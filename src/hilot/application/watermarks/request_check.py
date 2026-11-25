from dataclasses import dataclass
from pathlib import Path

from hilot.application.media.links import SupportedLinkFinder
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    MessageMediaReader,
    ProgressIndicator,
)
from hilot.domain.interfaces.adapters.watermark_detector import DetectableMediaMatcher
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.interfaces.adapters.watermark_scheduler import (
    WatermarkCheckScheduler,
    WatermarkReplyScheduler,
)
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.value_objects.download import DownloadPurpose, DownloadRequest, DownloadTrigger
from hilot.domain.value_objects.media import AttachedMedia, StorageKey
from hilot.domain.value_objects.message import (
    AnswerEntry,
    AnswerKind,
    CommandAnswer,
    Link,
    MediaLocation,
    SourceMessage,
)
from hilot.domain.value_objects.text import RichText
from hilot.domain.value_objects.watermark import (
    MediaLabel,
    WatermarkCheckRequest,
    WatermarkFailure,
    WatermarkReply,
    WatermarkResult,
    WatermarkTarget,
)

from .media import find_media_failure


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestWatermarkCheckDTO:
    source: SourceMessage

    # a command with links of its own checks their media, one without them the media it replies to with the rest of its album, or else the links there
    media_location: MediaLocation | None
    links: list[Link]


class RequestWatermarkCheck:
    def __init__(
        self,
        *,
        media_reader: MessageMediaReader,
        media_matcher: DetectableMediaMatcher,
        link_finder: SupportedLinkFinder,
        command_answerer: CommandAnswerer,
        progress_indicator: ProgressIndicator,
        watermark_formatter: WatermarkFormatter,
        workspace: Workspace,
        file_storage: FileStorage,
        download_scheduler: DownloadScheduler,
        check_scheduler: WatermarkCheckScheduler,
        reply_scheduler: WatermarkReplyScheduler,
    ) -> None:
        self._media_reader: MessageMediaReader = media_reader
        self._media_matcher: DetectableMediaMatcher = media_matcher
        self._link_finder: SupportedLinkFinder = link_finder
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._watermark_formatter: WatermarkFormatter = watermark_formatter
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._download_scheduler: DownloadScheduler = download_scheduler
        self._check_scheduler: WatermarkCheckScheduler = check_scheduler
        self._reply_scheduler: WatermarkReplyScheduler = reply_scheduler

    async def __call__(self, data: RequestWatermarkCheckDTO) -> None:
        media: list[AttachedMedia] = (
            await self._media_reader.read_album(data.media_location)
            if data.media_location is not None
            else []
        )

        if media:
            await self._check_media(source=data.source, media=media)

            return

        links: list[Link] = await self._link_finder.find_supported_links(data.links)

        if not links:
            await self._reply_failure(source=data.source, failure=WatermarkFailure.NO_MEDIA)

            return

        await self._show_progress(data.source)

        # the downloader takes the media of the links, the files only up to the detector's limit
        await self._download_scheduler.schedule_download(
            DownloadRequest(
                source=data.source,
                trigger=DownloadTrigger.COMMAND,
                purpose=DownloadPurpose.WATERMARK_CHECK,
                links=links,
                reply_to=data.source.message_id,
                size_limit=self._media_matcher.get_size_limit(),
            )
        )

    async def _check_media(self, *, source: SourceMessage, media: list[AttachedMedia]) -> None:
        accepted: list[tuple[MediaLabel, AttachedMedia]] = []
        failures: list[WatermarkResult] = []

        for position, item in enumerate(media, start=1):
            # a media alone needs no name, the media of an album go by their place in it
            label: MediaLabel = (
                MediaLabel(link=None, position=position) if len(media) > 1 else MediaLabel.empty()
            )
            failure: WatermarkFailure | None = find_media_failure(
                media_matcher=self._media_matcher, mime_type=item.mime_type, size=item.size
            )

            if failure is None:
                accepted.append((label, item))
            else:
                failures.append(WatermarkResult(label=label, outcome=failure))

        # the media the detector can't take are answered without a check
        if not accepted:
            await self._reply_scheduler.schedule_reply(
                WatermarkReply(source=source, results=failures)
            )

            return

        await self._show_progress(source)

        await self._check_scheduler.schedule_check(
            WatermarkCheckRequest(
                source=source,
                targets=[
                    await self._store_media(label=label, media=item) for label, item in accepted
                ],
                failures=failures,
            )
        )

    async def _store_media(self, *, label: MediaLabel, media: AttachedMedia) -> WatermarkTarget:
        async with self._workspace.create() as directory:
            path: Path = await self._media_reader.download_media(media=media, directory=directory)
            storage_key: StorageKey = await self._file_storage.upload(path)

        return WatermarkTarget(
            storage_key=storage_key,
            mime_type=media.mime_type,
            size=media.size,
            is_shared=False,
            label=label,
        )

    # the command is called on purpose, so unlike a link it shows progress in groups too
    async def _show_progress(self, source: SourceMessage) -> None:
        if source.allows_reactions():
            await self._progress_indicator.show_progress(source)

    async def _reply_failure(self, *, source: SourceMessage, failure: WatermarkFailure) -> None:
        await self._command_answerer.answer_command(
            source=source,
            answer=CommandAnswer(
                entries=[
                    AnswerEntry(
                        kind=AnswerKind.ERROR,
                        text=RichText.plain(self._watermark_formatter.format_outcome(failure)),
                    )
                ]
            ),
        )
