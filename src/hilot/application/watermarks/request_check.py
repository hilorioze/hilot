from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from hilot.application.media.links import SupportedLinkFinder
from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.entities.telegram_file_hash import TelegramFileHash
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.file_hasher import FileHasher
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
from hilot.domain.interfaces.repositories.cached_watermark_check import (
    CachedWatermarkCheckRepository,
)
from hilot.domain.interfaces.repositories.telegram_file_hash import TelegramFileHashRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.download import DownloadPurpose, DownloadRequest, DownloadTrigger
from hilot.domain.value_objects.media import AttachedMedia, ContentHash, StorageKey
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
    WatermarkCheck,
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
        file_hasher: FileHasher,
        telegram_file_hash_repository: TelegramFileHashRepository,
        cached_watermark_check_repository: CachedWatermarkCheckRepository,
        uow: UnitOfWork,
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
        self._file_hasher: FileHasher = file_hasher
        self._telegram_file_hash_repository: TelegramFileHashRepository = (
            telegram_file_hash_repository
        )
        self._cached_watermark_check_repository: CachedWatermarkCheckRepository = (
            cached_watermark_check_repository
        )
        self._uow: UnitOfWork = uow
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
        # each media in its order: the one to download and check, or its outcome known already
        entries: list[tuple[MediaLabel, AttachedMedia] | WatermarkResult] = []

        for position, item in enumerate(media, start=1):
            # a media alone needs no name, the media of an album go by their place in it
            label: MediaLabel = (
                MediaLabel(link=None, position=position) if len(media) > 1 else MediaLabel.empty()
            )
            outcome: WatermarkFailure | WatermarkCheck | None = find_media_failure(
                media_matcher=self._media_matcher, mime_type=item.mime_type, size=item.size
            ) or await self._find_known_check(item)

            entries.append(
                (label, item) if outcome is None else WatermarkResult(label=label, outcome=outcome)
            )

        # the media the detector can't take or has checked before are answered without a check
        if all(isinstance(entry, WatermarkResult) for entry in entries):
            await self._reply_scheduler.schedule_reply(
                WatermarkReply(
                    source=source,
                    results=[entry for entry in entries if isinstance(entry, WatermarkResult)],
                )
            )

            return

        await self._show_progress(source)

        await self._check_scheduler.schedule_check(
            WatermarkCheckRequest(
                source=source,
                media=[
                    entry
                    if isinstance(entry, WatermarkResult)
                    else await self._store_media(label=entry[0], media=entry[1])
                    for entry in entries
                ],
            )
        )

    # a file sent or forwarded again keeps its telegram id, so its verdict needs no download
    async def _find_known_check(self, media: AttachedMedia) -> WatermarkCheck | None:
        async with self._uow:
            telegram_file_hash: (
                TelegramFileHash | None
            ) = await self._telegram_file_hash_repository.get(media.file_unique_id)

            if telegram_file_hash is None:
                return None

            cached_watermark_check: (
                CachedWatermarkCheck | None
            ) = await self._cached_watermark_check_repository.get(telegram_file_hash.content_hash)

        if cached_watermark_check is None or not cached_watermark_check.is_fresh(
            datetime.now(UTC)
        ):
            return None

        return cached_watermark_check.check

    async def _store_media(self, *, label: MediaLabel, media: AttachedMedia) -> WatermarkTarget:
        async with self._workspace.create() as directory:
            path: Path = await self._media_reader.download_media(media=media, directory=directory)
            content_hash: ContentHash = await self._file_hasher.hash_file(path)
            storage_key: StorageKey = await self._file_storage.upload(path)

        async with self._uow:
            await self._telegram_file_hash_repository.save(
                TelegramFileHash(file_unique_id=media.file_unique_id, content_hash=content_hash)
            )

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
