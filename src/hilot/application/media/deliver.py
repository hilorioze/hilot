from contextlib import suppress
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import ClassVar

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.errors.messenger import (
    AlreadySentError,
    FileReferenceExpiredError,
    MessageGoneError,
)
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    MediaRefresher,
    MediaSender,
    MediaUploader,
    ProgressIndicator,
    TextSender,
)
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.cached_file import CachedFileRepository
from hilot.domain.interfaces.repositories.delivered_part import DeliveredPartRepository
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.download import DownloadRequest, DownloadResult, Failure
from hilot.domain.value_objects.media import FileId, MediaKind, StoredMedia
from hilot.domain.value_objects.message import Link, MessageId, SourceMessage

from .converters import convert_stored_media_to_file


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliverMediaDTO:
    result: DownloadResult


class DeliverMedia:
    # telegram takes up to 10 media in one album
    _ALBUM_SIZE: ClassVar[int] = 10

    def __init__(
        self,
        *,
        progress_indicator: ProgressIndicator,
        media_uploader: MediaUploader,
        media_sender: MediaSender,
        media_refresher: MediaRefresher,
        text_sender: TextSender,
        failure_formatter: FailureFormatter,
        file_storage: FileStorage,
        workspace: Workspace,
        download_scheduler: DownloadScheduler,
        delivered_part_repository: DeliveredPartRepository,
        cached_file_repository: CachedFileRepository,
        stored_file_repository: StoredFileRepository,
        uow: UnitOfWork,
    ) -> None:
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._media_uploader: MediaUploader = media_uploader
        self._media_sender: MediaSender = media_sender
        self._media_refresher: MediaRefresher = media_refresher
        self._text_sender: TextSender = text_sender
        self._failure_formatter: FailureFormatter = failure_formatter
        self._file_storage: FileStorage = file_storage
        self._workspace: Workspace = workspace
        self._download_scheduler: DownloadScheduler = download_scheduler
        self._delivered_part_repository: DeliveredPartRepository = delivered_part_repository
        self._cached_file_repository: CachedFileRepository = cached_file_repository
        self._stored_file_repository: StoredFileRepository = stored_file_repository
        self._uow: UnitOfWork = uow

    async def __call__(self, data: DeliverMediaDTO) -> None:
        source: SourceMessage = data.result.request.source

        # the reaction stands for the download, the upload shows its own progress
        if source.shows_progress():
            await self._progress_indicator.hide_progress(source)

        try:
            await self._deliver(data.result)
        # a cached file whose message is gone is downloaded again
        except MessageGoneError:
            if source.shows_progress():
                await self._progress_indicator.show_progress(source)

            await self._download_scheduler.schedule_download(data.result.request)

    async def _deliver(self, result: DownloadResult) -> None:
        source: SourceMessage = result.request.source

        async with self._uow:
            delivered_parts: list[DeliveredPart] = await self._delivered_part_repository.get_all(
                source
            )

        for part, content in enumerate(self._split_parts(result)):
            delivered_part: DeliveredPart = DeliveredPart(
                account_id=source.account_id,
                chat_id=source.chat_id,
                message_id=source.message_id,
                part=part,
            )

            if delivered_part in delivered_parts:
                continue

            cached_files: list[CachedFile] = []
            stored_files: list[StoredFile] = []

            # a duplicate send means an earlier attempt delivered the part but crashed before saving it
            with suppress(AlreadySentError):
                if isinstance(content, Failure):
                    await self._send_failure(request=result.request, part=part, failure=content)
                else:
                    cached_files = await self._send_media(source=source, part=part, media=content)
                    stored_files = [
                        convert_stored_media_to_file(item)
                        for item in content
                        if isinstance(item, StoredMedia)
                    ]

            async with self._uow:
                await self._delivered_part_repository.add(delivered_part)

                for cached_file in cached_files:
                    await self._cached_file_repository.save(cached_file)

                # let other accounts reuse the sent files until the file storage expires them
                for stored_file in stored_files:
                    await self._stored_file_repository.save(stored_file)

    def _split_parts(
        self, result: DownloadResult
    ) -> list[tuple[StoredMedia | CachedFile, ...] | Failure]:
        visual_media: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind != MediaKind.AUDIO
        ]
        audio: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind == MediaKind.AUDIO
        ]
        failures: list[Failure] = (
            result.failures if result.request.source.reports_failures() else []
        )

        return [
            *batched(visual_media, self._ALBUM_SIZE, strict=False),
            *batched(audio, self._ALBUM_SIZE, strict=False),
            *failures,
        ]

    async def _send_failure(
        self, *, request: DownloadRequest, part: int, failure: Failure
    ) -> None:
        text: str = self._failure_formatter.format_failure(
            failure=failure, size_limit=request.size_limit
        )

        # quote the failed link when the message has several
        quote: Link | None = failure.link if len(request.links) > 1 else None

        await self._text_sender.send_text(source=request.source, part=part, text=text, quote=quote)

    async def _send_media(
        self, *, source: SourceMessage, part: int, media: tuple[StoredMedia | CachedFile, ...]
    ) -> list[CachedFile]:
        files: list[FileId] = [
            await self._get_file_id(source=source, media=item) for item in media
        ]

        try:
            message_ids: list[MessageId] = await self._media_sender.send_media(
                source=source, part=part, files=files
            )
        except FileReferenceExpiredError:
            files = [
                await self._refresh_file_id(item) if isinstance(item, CachedFile) else file_id
                for item, file_id in zip(media, files, strict=True)
            ]
            message_ids = await self._media_sender.send_media(
                source=source, part=part, files=files
            )

        return [
            CachedFile(
                account_id=source.account_id,
                media_key=item.media_key,
                kind=item.kind,
                file_id=file_id,
                chat_id=source.chat_id,
                message_id=message_id,
            )
            for item, file_id, message_id in zip(media, files, message_ids, strict=True)
        ]

    async def _get_file_id(
        self, *, source: SourceMessage, media: StoredMedia | CachedFile
    ) -> FileId:
        if isinstance(media, CachedFile):
            return media.file_id

        async with self._workspace.create() as directory:
            path: Path = directory / media.file_name
            await self._file_storage.download(key=media.storage_key, path=path)

            return await self._media_uploader.upload_media(
                chat_id=source.chat_id,
                media=media,
                path=path,
                shows_progress=source.shows_progress(),
            )

    async def _refresh_file_id(self, cached_file: CachedFile) -> FileId:
        try:
            return await self._media_refresher.refresh_media(cached_file)
        except MessageGoneError:
            async with self._uow:
                await self._cached_file_repository.delete(cached_file)

            raise
