from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import batched, groupby
from pathlib import Path
from typing import ClassVar

from hilot.domain.entities.bot_file import BotFile
from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.delivered_part import DeliveredPart
from hilot.domain.errors.messenger import (
    AlreadySentError,
    FileReferenceExpiredError,
    MessageGoneError,
    RichUnavailableError,
)
from hilot.domain.interfaces.adapters.caption_formatter import CaptionFormatter
from hilot.domain.interfaces.adapters.delivery_formatter import DeliveryFormatter
from hilot.domain.interfaces.adapters.download_scheduler import DownloadScheduler
from hilot.domain.interfaces.adapters.failure_formatter import FailureFormatter
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.messenger import (
    CaptionLimitReader,
    CommandAnswerer,
    MediaAttacher,
    MediaRefresher,
    MediaSender,
    MediaUploader,
    MessageMediaReader,
    MessageReader,
    ProgressIndicator,
    RichLimitReader,
    RichMediaUploader,
    RichSender,
    TextSender,
)
from hilot.domain.interfaces.adapters.text_measurer import TextMeasurer
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.bot_file import BotFileRepository
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
    AttachedMedia,
    FileId,
    MediaInfo,
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
    MediaLocation,
    MessageId,
    SourceMessage,
)
from hilot.domain.value_objects.rich import RichMedia, RichMessage
from hilot.domain.value_objects.text import RichText


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliverMediaDTO:
    result: DownloadResult


# media that go out in one message: an album of the account, or a rich message of the inline bot
@dataclass(frozen=True, slots=True, kw_only=True)
class _MediaPart:
    media: tuple[StoredMedia | CachedFile, ...]

    is_rich: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _SentPart:
    message_ids: list[MessageId]

    # only the account's own uploads are sent again from the cache
    cached_files: list[CachedFile]


class DeliverMedia:
    # telegram takes up to 10 media in one album
    _ALBUM_SIZE: ClassVar[int] = 10

    # and up to 50 in one rich message
    _RICH_MEDIA_LIMIT: ClassVar[int] = 50

    def __init__(
        self,
        *,
        progress_indicator: ProgressIndicator,
        message_reader: MessageReader,
        message_media_reader: MessageMediaReader,
        media_uploader: MediaUploader,
        media_sender: MediaSender,
        media_attacher: MediaAttacher,
        media_refresher: MediaRefresher,
        rich_limit_reader: RichLimitReader,
        rich_media_uploader: RichMediaUploader,
        rich_sender: RichSender,
        text_sender: TextSender,
        command_answerer: CommandAnswerer,
        failure_formatter: FailureFormatter,
        delivery_formatter: DeliveryFormatter,
        caption_formatter: CaptionFormatter,
        caption_limit_reader: CaptionLimitReader,
        text_measurer: TextMeasurer,
        file_storage: FileStorage,
        workspace: Workspace,
        download_scheduler: DownloadScheduler,
        delivered_part_repository: DeliveredPartRepository,
        cached_file_repository: CachedFileRepository,
        bot_file_repository: BotFileRepository,
        uow: UnitOfWork,
    ) -> None:
        self._progress_indicator: ProgressIndicator = progress_indicator
        self._message_reader: MessageReader = message_reader
        self._message_media_reader: MessageMediaReader = message_media_reader
        self._media_uploader: MediaUploader = media_uploader
        self._media_sender: MediaSender = media_sender
        self._media_attacher: MediaAttacher = media_attacher
        self._media_refresher: MediaRefresher = media_refresher
        self._rich_limit_reader: RichLimitReader = rich_limit_reader
        self._rich_media_uploader: RichMediaUploader = rich_media_uploader
        self._rich_sender: RichSender = rich_sender
        self._text_sender: TextSender = text_sender
        self._command_answerer: CommandAnswerer = command_answerer
        self._failure_formatter: FailureFormatter = failure_formatter
        self._delivery_formatter: DeliveryFormatter = delivery_formatter
        self._caption_formatter: CaptionFormatter = caption_formatter
        self._caption_limit_reader: CaptionLimitReader = caption_limit_reader
        self._text_measurer: TextMeasurer = text_measurer
        self._file_storage: FileStorage = file_storage
        self._workspace: Workspace = workspace
        self._download_scheduler: DownloadScheduler = download_scheduler
        self._delivered_part_repository: DeliveredPartRepository = delivered_part_repository
        self._cached_file_repository: CachedFileRepository = cached_file_repository
        self._bot_file_repository: BotFileRepository = bot_file_repository
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
            if any(delivered_part.part == part for delivered_part in delivered_parts):
                continue

            # the message can be deleted while the earlier parts upload
            if part and not await self._message_reader.message_exists(source):
                return

            sent: _SentPart = _SentPart(message_ids=[], cached_files=[])

            # a duplicate send means an earlier attempt delivered the part but crashed before saving it
            with suppress(AlreadySentError):
                if isinstance(content, Failure):
                    await self._send_failure(request=result.request, part=part, failure=content)
                elif content.is_rich:
                    sent = await self._send_rich(request=request, part=part, media=content.media)
                else:
                    sent = await self._send_media(
                        request=request,
                        part=part,
                        media=content.media,
                        attaches=result.attaches_media(),
                        first_index=0,
                    )

            async with self._uow:
                await self._delivered_part_repository.add(
                    DeliveredPart(
                        account_id=source.account_id,
                        chat_id=source.chat_id,
                        message_id=source.message_id,
                        part=part,
                        message_ids=sent.message_ids,
                        delivered_at=datetime.now(UTC),
                    )
                )

                for cached_file in sent.cached_files:
                    await self._cached_file_repository.save(cached_file)

        if request.answers_command():
            await self._answer_command(result)

    # the command names each post it delivered and leads to its media, then each failure
    async def _answer_command(self, result: DownloadResult) -> None:
        request: DownloadRequest = result.request
        posts: list[DeliveredPost] = await self._find_delivered_posts(result)

        # a command that became the media answers itself
        if any(post.message_id == request.source.message_id for post in posts):
            return

        entries: list[AnswerEntry] = [
            *(
                AnswerEntry(
                    kind=AnswerKind.RESULT,
                    text=self._delivery_formatter.format_delivered_post(post),
                )
                for post in posts
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

    # the delivered parts keep the messages of their media, the ones an earlier attempt delivered too
    async def _find_delivered_posts(self, result: DownloadResult) -> list[DeliveredPost]:
        source: SourceMessage = result.request.source

        async with self._uow:
            delivered_parts: list[DeliveredPart] = await self._delivered_part_repository.get_all(
                source
            )

        message_ids: dict[int, list[MessageId]] = {
            delivered_part.part: delivered_part.message_ids for delivered_part in delivered_parts
        }
        media: dict[PostDetails, list[tuple[MediaInfo, MessageId]]] = {}

        for part, content in enumerate(self._split_parts(result)):
            if isinstance(content, Failure):
                continue

            # a part sent by an attempt that crashed before saving it has no messages
            for item, message_id in zip(content.media, message_ids.get(part, []), strict=False):
                media.setdefault(item.post, []).append((item.info, message_id))

        return [
            DeliveredPost(
                post=post,
                media=[info for info, _ in items],
                chat_id=source.chat_id,
                message_id=min(message_id for _, message_id in items),
            )
            for post, items in media.items()
        ]

    def _split_parts(self, result: DownloadResult) -> list[_MediaPart | Failure]:
        visual_media: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind != MediaKind.AUDIO
        ]
        audio: list[StoredMedia | CachedFile] = [
            media for media in result.media if media.kind == MediaKind.AUDIO
        ]
        # a command reports its failures in its answer
        failures: list[Failure] = (
            result.failures
            if result.request.reports_failures() and not result.request.answers_command()
            else []
        )

        return [*self._split_media(visual_media), *self._split_media(audio), *failures]

    # a post that needs a rich message goes alone, the others share the albums in their order
    def _split_media(self, media: list[StoredMedia | CachedFile]) -> list[_MediaPart]:
        parts: list[_MediaPart] = []

        for is_rich, runs in groupby(
            (list(items) for _, items in groupby(media, key=lambda item: item.post)),
            key=self._needs_rich,
        ):
            if is_rich:
                parts.extend(
                    _MediaPart(media=chunk, is_rich=True)
                    for items in runs
                    for chunk in batched(items, self._RICH_MEDIA_LIMIT, strict=False)
                )
            else:
                parts.extend(
                    _MediaPart(media=chunk, is_rich=False)
                    for chunk in batched(
                        (item for items in runs for item in items), self._ALBUM_SIZE, strict=False
                    )
                )

        return parts

    # a post whose caption doesn't fit or which doesn't fit an album; a post without text needs no rich message
    def _needs_rich(self, media: list[StoredMedia | CachedFile]) -> bool:
        caption: RichText | None = self._caption_formatter.format_caption(
            post=media[0].post, limit=None
        )

        if caption is None:
            return False

        return (
            len(media) > self._ALBUM_SIZE
            or self._text_measurer.measure(caption.get_text())
            > self._caption_limit_reader.get_caption_limit()
        ) and all(
            item.info.size <= self._rich_limit_reader.get_rich_upload_limit() for item in media
        )

    async def _send_failure(
        self, *, request: DownloadRequest, part: int, failure: Failure
    ) -> None:
        text: str = self._failure_formatter.format_failure(
            failure=failure, size_limit=request.size_limit
        )

        # quote the failed link when the message has several
        quote: Link | None = failure.link if len(request.links) > 1 else None

        await self._text_sender.send_text(source=request.source, part=part, text=text, quote=quote)

    # a chat without the inline bot gets the albums of the account instead
    async def _send_rich(
        self, *, request: DownloadRequest, part: int, media: tuple[StoredMedia | CachedFile, ...]
    ) -> _SentPart:
        try:
            files: list[FileId] = [
                await self._get_bot_file_id(request=request, media=item) for item in media
            ]
            message_id: MessageId = await self._rich_sender.send_rich(
                source=request.source,
                part=part,
                message=RichMessage(
                    media=[
                        RichMedia(kind=item.kind, file_id=file_id)
                        for item, file_id in zip(media, files, strict=True)
                    ],
                    text=self._caption_formatter.format_caption(
                        post=media[0].post, limit=self._rich_limit_reader.get_rich_text_limit()
                    ),
                ),
                reply_to=request.reply_to,
            )
        except RichUnavailableError:
            sent: list[_SentPart] = [
                await self._send_media(
                    request=request,
                    part=part,
                    media=chunk,
                    attaches=False,
                    first_index=index * self._ALBUM_SIZE,
                )
                for index, chunk in enumerate(batched(media, self._ALBUM_SIZE, strict=False))
            ]

            return _SentPart(
                message_ids=[message_id for item in sent for message_id in item.message_ids],
                cached_files=[cached_file for item in sent for cached_file in item.cached_files],
            )

        return _SentPart(message_ids=[message_id] * len(media), cached_files=[])

    async def _send_media(
        self,
        *,
        request: DownloadRequest,
        part: int,
        media: tuple[StoredMedia | CachedFile, ...],
        attaches: bool,
        first_index: int,
    ) -> _SentPart:
        source: SourceMessage = request.source
        files: list[FileId] = [
            await self._get_file_id(request=request, media=item) for item in media
        ]

        try:
            message_ids: list[MessageId] = await self._place_media(
                request=request,
                part=part,
                media=media,
                files=files,
                attaches=attaches,
                first_index=first_index,
            )
        except FileReferenceExpiredError:
            files = [
                await self._refresh_file_id(item) if isinstance(item, CachedFile) else file_id
                for item, file_id in zip(media, files, strict=True)
            ]
            message_ids = await self._place_media(
                request=request,
                part=part,
                media=media,
                files=files,
                attaches=attaches,
                first_index=first_index,
            )

        return _SentPart(
            message_ids=message_ids,
            cached_files=[
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
            ],
        )

    async def _place_media(
        self,
        *,
        request: DownloadRequest,
        part: int,
        media: tuple[StoredMedia | CachedFile, ...],
        files: list[FileId],
        attaches: bool,
        first_index: int,
    ) -> list[MessageId]:
        source: SourceMessage = request.source

        if attaches:
            caption: RichText = self._attach_caption(source=source, post=media[0].post)

            # the text of the message and the whole caption may not fit together, then the media answers the message
            if (
                self._text_measurer.measure(caption.get_text())
                <= self._caption_limit_reader.get_caption_limit()
            ):
                await self._media_attacher.attach_media(
                    source=source, media=OutgoingMedia(file_id=files[0], caption=caption)
                )

                return [source.message_id]

        return await self._media_sender.send_media(
            source=source,
            part=part,
            first_index=first_index,
            media=self._caption_media(media=media, files=files),
            reply_to=request.reply_to,
        )

    def _attach_caption(self, *, source: SourceMessage, post: PostDetails) -> RichText:
        caption: RichText | None = self._caption_formatter.format_caption(post=post, limit=None)

        return RichText.join(
            separator="\n\n",
            texts=[RichText.plain(source.text), *((caption,) if caption else ())],
        )

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
            return await self._media_uploader.upload_media(
                chat_id=request.source.chat_id,
                media=media,
                path=await self._download_stored_media(media=media, directory=directory),
                shows_progress=request.shows_progress(),
            )

    # the inline bot uploads a file once, from the bucket or from the account's message holding it
    async def _get_bot_file_id(
        self, *, request: DownloadRequest, media: StoredMedia | CachedFile
    ) -> FileId:
        async with self._uow:
            bot_file: BotFile | None = await self._bot_file_repository.get(media.media_key)

        if bot_file is not None:
            return bot_file.file_id

        async with self._workspace.create() as directory:
            file_id: FileId = await self._rich_media_uploader.upload_rich_media(
                account_id=request.source.account_id,
                media=media,
                path=await self._download_stored_media(media=media, directory=directory)
                if isinstance(media, StoredMedia)
                else await self._download_cached_file(cached_file=media, directory=directory),
            )

        async with self._uow:
            await self._bot_file_repository.save(
                BotFile(media_key=media.media_key, file_id=file_id)
            )

        return file_id

    async def _download_stored_media(self, *, media: StoredMedia, directory: Path) -> Path:
        path: Path = directory / media.file_name
        await self._file_storage.download(key=media.storage_key, path=path)

        return path

    async def _download_cached_file(self, *, cached_file: CachedFile, directory: Path) -> Path:
        # the message gives a fresh file reference
        try:
            attached: AttachedMedia | None = await self._message_media_reader.read_media(
                MediaLocation(
                    chat_id=cached_file.chat_id,
                    message_id=cached_file.message_id,
                    is_external_reply=False,
                )
            )
        except MessageGoneError:
            await self._forget_cached_file(cached_file)

            raise

        # the owner can edit the media out of the message
        if attached is None:
            await self._forget_cached_file(cached_file)

            raise MessageGoneError

        return await self._message_media_reader.download_media(media=attached, directory=directory)

    async def _refresh_file_id(self, cached_file: CachedFile) -> FileId:
        try:
            return await self._media_refresher.refresh_media(cached_file)
        except MessageGoneError:
            await self._forget_cached_file(cached_file)

            raise

    async def _forget_cached_file(self, cached_file: CachedFile) -> None:
        async with self._uow:
            await self._cached_file_repository.delete(cached_file)
