from contextlib import suppress
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import ClassVar

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.errors.messenger import (
    AlreadySentError,
    FileReferenceExpiredError,
    MessageGoneError,
)
from hilot.domain.interfaces.adapters.caption_formatter import CaptionFormatter
from hilot.domain.interfaces.adapters.delivery_formatter import DeliveryFormatter
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CaptionLimitReader,
    CommandAnswerer,
    MediaRefresher,
    MediaSender,
    MediaUploader,
    MessageReader,
    ProgressIndicator,
    TextSender,
)
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.cached_file import CachedFileRepository
from hilot.domain.interfaces.repositories.delivered_part import DeliveredPartRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.download import (
    DeliveredPost,
    DownloadRequest,
    DownloadResult,
    Failure,
)
from hilot.domain.value_objects.media import (
    FileId,
    MediaKind,
    OutgoingMedia,
    PostDetails,
    StoredMedia,
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
        message_reader: MessageReader,
        media_uploader: MediaUploader,
        media_sender: MediaSender,
        media_refresher: MediaRefresher,
        text_sender: TextSender,
        command_answerer: CommandAnswerer,
        failure_formatter: FailureFormatter,
        delivery_formatter: DeliveryFormatter,
        caption_formatter: CaptionFormatter,
        caption_limit_reader: CaptionLimitReader,
        file_storage: FileStorage,
        workspace: Workspace,
        download_scheduler: DownloadScheduler,
        delivered_part_repository: DeliveredPartRepository,
        cached_file_repository: CachedFileRepository,
        uow: UnitOfWork,
    ) -> None:
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._message_reader: MessageReader = message_reader
        self._media_uploader: MediaUploader = media_uploader
        self._media_sender: MediaSender = media_sender
        self._media_refresher: MediaRefresher = media_refresher
        self._text_sender: TextSender = text_sender
        self._command_answerer: CommandAnswerer = command_answerer
        self._failure_formatter: FailureFormatter = failure_formatter
        self._delivery_formatter: DeliveryFormatter = delivery_formatter
        self._caption_formatter: CaptionFormatter = caption_formatter
        self._caption_limit_reader: CaptionLimitReader = caption_limit_reader
        self._file_storage: FileStorage = file_storage
        self._workspace: Workspace = workspace
        self._download_scheduler: DownloadScheduler = download_scheduler
        self._delivered_part_repository: DeliveredPartRepository = delivered_part_repository
        self._cached_file_repository: CachedFileRepository = cached_file_repository
        self._uow: UnitOfWork = uow

    async def __call__(self, data: DeliverMediaDTO) -> None:
        request: DownloadRequest = data.result.request
        source: SourceMessage = request.source

        # a message sent by mistake and deleted right away gets no reply
        if not await self._message_reader.message_exists(source):
            return

        # the reaction stands for the download, the upload shows its own progress
        if request.shows_progress():
            await self._progress_indicator.hide_progress(source)

        try:
            await self._deliver(data.result)
        # a cached file whose message is gone is downloaded again
        except MessageGoneError:
            if request.shows_progress():
                await self._progress_indicator.show_progress(source)

            await self._download_scheduler.schedule_download(data.result.request)

    async def _deliver(self, result: DownloadResult) -> None:
        request: DownloadRequest = result.request
        source: SourceMessage = request.source

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

            # the message can be deleted while the earlier parts upload
            if part and not await self._message_reader.message_exists(source):
                return

            cached_files: list[CachedFile] = []

            # a duplicate send means an earlier attempt delivered the part but crashed before saving it
            with suppress(AlreadySentError):
                if isinstance(content, Failure):
                    await self._send_failure(request=result.request, part=part, failure=content)
                else:
                    cached_files = await self._send_media(
                        request=request, part=part, media=content
                    )

            async with self._uow:
                await self._delivered_part_repository.add(delivered_part)

                for cached_file in cached_files:
                    await self._cached_file_repository.save(cached_file)

        if request.answers_in_command():
            await self._answer_command(result)

    # the command names each post it delivered and leads to its media, then each failure
    async def _answer_command(self, result: DownloadResult) -> None:
        request: DownloadRequest = result.request
        entries: list[AnswerEntry] = [
            *(
                AnswerEntry(
                    kind=AnswerKind.RESULT,
                    text=self._delivery_formatter.format_delivered_post(post),
                )
                for post in await self._find_delivered_posts(result)
            ),
            *(
                AnswerEntry(kind=AnswerKind.ERROR, text=RichText.plain(text))
                for text in self._failure_formatter.format_failures(
                    failures=result.failures,
                    size_limit=request.size_limit,
                    names_links=request.names_links(),
                )
            ),
        ]

        await self._command_answerer.answer_command(
            source=request.source,
            answer=CommandAnswer(
                entries=entries
                or [
                    AnswerEntry(
                        kind=AnswerKind.ERROR,
                        text=RichText.plain(self._failure_formatter.format_no_media()),
                    )
                ]
            ),
        )

    # the cached files point at the messages of every part, the ones an earlier attempt delivered too
    async def _find_delivered_posts(self, result: DownloadResult) -> list[DeliveredPost]:
        files: dict[PostDetails, list[CachedFile]] = {}

        async with self._uow:
            for media in result.media:
                cached_file: CachedFile | None = await self._cached_file_repository.get(
                    account_id=result.request.source.account_id, media_key=media.media_key
                )

                # a later delivery of the same media to another chat replaces its cached file
                if (
                    cached_file is not None
                    and cached_file.chat_id == result.request.source.chat_id
                ):
                    files.setdefault(cached_file.post, []).append(cached_file)

        return [
            DeliveredPost(
                post=post,
                media=[cached_file.info for cached_file in cached_files],
                chat_id=cached_files[0].chat_id,
                message_id=min(cached_file.message_id for cached_file in cached_files),
            )
            for post, cached_files in files.items()
        ]

    def _split_parts(
        self, result: DownloadResult
    ) -> list[tuple[StoredMedia | CachedFile, ...] | Failure]:
        visual_media: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind != MediaKind.AUDIO
        ]
        audio: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind == MediaKind.AUDIO
        ]
        # a command in reply to links reports its failures in its own text
        failures: list[Failure] = (
            result.failures
            if result.request.reports_failures() and not result.request.answers_in_command()
            else []
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
        self, *, request: DownloadRequest, part: int, media: tuple[StoredMedia | CachedFile, ...]
    ) -> list[CachedFile]:
        source: SourceMessage = request.source
        files: list[FileId] = [
            await self._get_file_id(request=request, media=item) for item in media
        ]

        try:
            message_ids: list[MessageId] = await self._media_sender.send_media(
                source=source,
                part=part,
                media=self._caption_media(media=media, files=files),
                reply_to=request.reply_to,
            )
        except FileReferenceExpiredError:
            files = [
                await self._refresh_file_id(item) if isinstance(item, CachedFile) else file_id
                for item, file_id in zip(media, files, strict=True)
            ]
            message_ids = await self._media_sender.send_media(
                source=source,
                part=part,
                media=self._caption_media(media=media, files=files),
                reply_to=request.reply_to,
            )

        return [
            CachedFile(
                account_id=source.account_id,
                media_key=item.media_key,
                file_id=file_id,
                info=item.info,
                chat_id=source.chat_id,
                message_id=message_id,
                post=item.post,
            )
            for item, file_id, message_id in zip(media, files, message_ids, strict=True)
        ]

    # an album shows the caption of each post once, on its first file
    def _caption_media(
        self, *, media: tuple[StoredMedia | CachedFile, ...], files: list[FileId]
    ) -> list[OutgoingMedia]:
        limit: int = self._caption_limit_reader.get_caption_limit()

        return [
            OutgoingMedia(
                file_id=file_id,
                caption=self._caption_formatter.format_caption(post=item.post, limit=limit)
                if index == 0 or item.post != media[index - 1].post
                else None,
            )
            for index, (item, file_id) in enumerate(zip(media, files, strict=True))
        ]

    async def _get_file_id(
        self, *, request: DownloadRequest, media: StoredMedia | CachedFile
    ) -> FileId:
        if isinstance(media, CachedFile):
            return media.file_id

        async with self._workspace.create() as directory:
            path: Path = directory / media.file_name
            await self._file_storage.download(key=media.storage_key, path=path)

            return await self._media_uploader.upload_media(
                chat_id=request.source.chat_id,
                media=media,
                path=path,
                shows_progress=request.shows_progress(),
            )

    async def _refresh_file_id(self, cached_file: CachedFile) -> FileId:
        try:
            return await self._media_refresher.refresh_media(cached_file)
        except MessageGoneError:
            async with self._uow:
                await self._cached_file_repository.delete(cached_file)

            raise
