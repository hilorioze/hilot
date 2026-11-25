from dataclasses import dataclass, replace
from pathlib import Path

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.errors.extraction import DownloadFailedError, TooBigError
from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.disk_space import DiskSpace
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.media_lock import MediaLock
from hilot.domain.interfaces.adapters.media_prober import MediaProber
from hilot.domain.interfaces.adapters.media_transcoder import MediaTranscoder
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.download import DownloadResult, Failure
from hilot.domain.value_objects.media import MediaInfo, StorageKey, StoredMedia

from .converters import convert_stored_file_to_media, convert_stored_media_to_file


@dataclass(frozen=True, slots=True, kw_only=True)
class TranscodeMediaDTO:
    result: DownloadResult


class TranscodeMedia:
    def __init__(
        self,
        *,
        workspace: Workspace,
        disk_space: DiskSpace,
        file_storage: FileStorage,
        media_transcoder: MediaTranscoder,
        media_prober: MediaProber,
        delivery_scheduler: DeliveryScheduler,
        stored_file_repository: StoredFileRepository,
        media_lock: MediaLock,
        uow: UnitOfWork,
    ) -> None:
        self._workspace: Workspace = workspace
        self._disk_space: DiskSpace = disk_space
        self._file_storage: FileStorage = file_storage
        self._media_transcoder: MediaTranscoder = media_transcoder
        self._media_prober: MediaProber = media_prober
        self._delivery_scheduler: DeliveryScheduler = delivery_scheduler
        self._stored_file_repository: StoredFileRepository = stored_file_repository
        self._media_lock: MediaLock = media_lock
        self._uow: UnitOfWork = uow

    async def __call__(self, data: TranscodeMediaDTO) -> None:
        items: list[StoredMedia | CachedFile | Failure] = [
            await self._transcode_media(media=media, size_limit=data.result.request.size_limit)
            for media in data.result.media
        ]

        result: DownloadResult = DownloadResult.from_items(
            request=data.result.request, items=[*items, *data.result.failures]
        )
        await self._delivery_scheduler.schedule_delivery(result)

    async def _transcode_media(
        self, *, media: StoredMedia | CachedFile, size_limit: int
    ) -> StoredMedia | CachedFile | Failure:
        if not isinstance(media, StoredMedia) or not media.info.needs_transcoding():
            return media

        # the accounts that get the same media at once wait for one transcode of it
        async with self._media_lock.acquire(media.media_key):
            async with self._uow:
                stored_file: StoredFile | None = await self._stored_file_repository.get(
                    media.media_key
                )

            # an earlier transcode replaced the original file with its own and deleted it
            source: StoredMedia = (
                media
                if stored_file is None
                else convert_stored_file_to_media(stored_file=stored_file, link=media.link)
            )

            if not source.info.needs_transcoding() and source.info.size <= size_limit:
                return source

            try:
                return await self._transcode_stored_media(media=source, size_limit=size_limit)
            except DownloadFailedError as error:
                return Failure.from_error(link=media.link, error=error)

    async def _transcode_stored_media(self, *, media: StoredMedia, size_limit: int) -> StoredMedia:
        async with (
            self._disk_space.reserve(media.info.size + size_limit),
            self._workspace.create() as source_directory,
            self._workspace.create() as output_directory,
        ):
            source: Path = source_directory / media.file_name
            await self._file_storage.download(key=media.storage_key, path=source)

            path: Path = await self._media_transcoder.transcode(
                path=source, kind=media.kind, directory=output_directory, size_limit=size_limit
            )
            info: MediaInfo = await self._media_prober.probe(path)

            # the transcoder cuts the output at the limit, so its real size stays unknown
            if info.size > size_limit:
                raise TooBigError(size=None)

            storage_key: StorageKey = await self._file_storage.upload(path)

        transcoded_media: StoredMedia = replace(
            media, storage_key=storage_key, file_name=path.name, info=info
        )

        # the other accounts and a retry of this transcode reuse the file until the file storage expires it
        async with self._uow:
            await self._stored_file_repository.save(convert_stored_media_to_file(transcoded_media))

        # only the transcodes take an original file, and from now on they take the transcoded one; a transcoded file may still wait for its delivery
        if media.info.needs_transcoding():
            await self._file_storage.delete(media.storage_key)

        return transcoded_media
