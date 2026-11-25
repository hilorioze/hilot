from dataclasses import dataclass
from pathlib import Path

from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CommandAnswerer,
    MessageMediaReader,
    ProgressIndicator,
)
from hilot.domain.interfaces.adapters.watermark_detector import DetectableMediaMatcher
from hilot.domain.interfaces.adapters.watermark_formatter import WatermarkFormatter
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkCheckScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.value_objects.media import AttachedMedia, StorageKey
from hilot.domain.value_objects.message import (
    AnswerKind,
    CommandAnswer,
    MediaLocation,
    SourceMessage,
)
from hilot.domain.value_objects.watermark import WatermarkCheckRequest, WatermarkFailure


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestWatermarkCheckDTO:
    source: SourceMessage

    media_location: MediaLocation


class RequestWatermarkCheck:
    def __init__(
        self,
        *,
        media_reader: MessageMediaReader,
        media_matcher: DetectableMediaMatcher,
        command_answerer: CommandAnswerer,
        progress_indicator: ProgressIndicator,
        watermark_formatter: WatermarkFormatter,
        workspace: Workspace,
        file_storage: FileStorage,
        check_scheduler: WatermarkCheckScheduler,
    ) -> None:
        self._media_reader: MessageMediaReader = media_reader
        self._media_matcher: DetectableMediaMatcher = media_matcher
        self._command_answerer: CommandAnswerer = command_answerer
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._watermark_formatter: WatermarkFormatter = watermark_formatter
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._check_scheduler: WatermarkCheckScheduler = check_scheduler

    async def __call__(self, data: RequestWatermarkCheckDTO) -> None:
        media: AttachedMedia | None = await self._media_reader.read_media(data.media_location)

        if media is None:
            await self._reply_failure(source=data.source, failure=WatermarkFailure.NO_MEDIA)

            return

        failure: WatermarkFailure | None = self._find_failure(media)

        if failure is not None:
            await self._reply_failure(source=data.source, failure=failure)

            return

        # the owner calls the command on purpose, so unlike a link it shows progress in groups too
        if data.source.allows_reactions():
            await self._progress_indicator.show_progress(data.source)

        async with self._workspace.create() as directory:
            path: Path = await self._media_reader.download_media(media=media, directory=directory)
            storage_key: StorageKey = await self._file_storage.upload(path)

        request: WatermarkCheckRequest = WatermarkCheckRequest(
            source=data.source, storage_key=storage_key, mime_type=media.mime_type
        )
        await self._check_scheduler.schedule_check(request)

    def _find_failure(self, media: AttachedMedia) -> WatermarkFailure | None:
        if not self._media_matcher.matches(media.mime_type):
            return WatermarkFailure.UNSUPPORTED

        if media.size > self._media_matcher.get_size_limit():
            return WatermarkFailure.TOO_BIG

        return None

    async def _reply_failure(self, *, source: SourceMessage, failure: WatermarkFailure) -> None:
        await self._command_answerer.answer_command(
            source=source,
            answer=CommandAnswer(
                kind=AnswerKind.ERROR, entries=[self._watermark_formatter.format_outcome(failure)]
            ),
        )
