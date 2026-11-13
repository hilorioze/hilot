from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.errors.extraction import DownloadFailedError, TooBigError
from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.disk_space import DiskSpace
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.media_prober import MediaProber
from hilot.domain.interfaces.adapters.media_transcoder import MediaTranscoder
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.value_objects.download import DownloadResult, Failure
from hilot.domain.value_objects.media import MediaInfo, StorageKey, StoredMedia


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
    ) -> None:
        self._workspace: Workspace = workspace
        self._disk_space: DiskSpace = disk_space
        self._file_storage: FileStorage = file_storage
        self._media_transcoder: MediaTranscoder = media_transcoder
        self._media_prober: MediaProber = media_prober
        self._delivery_scheduler: DeliveryScheduler = delivery_scheduler

    async def __call__(self, data: TranscodeMediaDTO) -> None:
        # a failed transcode deletes the media it stored and keeps the original ones for a retry
        async with AsyncExitStack() as uploads:
            items: list[StoredMedia | CachedFile | Failure] = [
                await self._transcode_media(
                    media=media, size_limit=data.result.request.size_limit, uploads=uploads
                )
                for media in data.result.media
            ]

            result: DownloadResult = DownloadResult.from_items(
                request=data.result.request, items=[*items, *data.result.failures]
            )
            await self._delivery_scheduler.schedule_delivery(result)

            # keep the uploads for the delivery
            uploads.pop_all()

        delivered_media: list[StoredMedia] = result.get_stored_media()

        # the delivery got the transcoded media instead of the original ones
        for media in data.result.get_stored_media():
            if media not in delivered_media:
                await self._file_storage.delete(media.storage_key)

    async def _transcode_media(
        self, *, media: StoredMedia | CachedFile, size_limit: int, uploads: AsyncExitStack
    ) -> StoredMedia | CachedFile | Failure:
        if not isinstance(media, StoredMedia) or not media.info.needs_transcoding():
            return media

        try:
            return await self._transcode_stored_media(
                media=media, size_limit=size_limit, uploads=uploads
            )
        except DownloadFailedError as error:
            return Failure.from_error(link=media.link, error=error)

    async def _transcode_stored_media(
        self, *, media: StoredMedia, size_limit: int, uploads: AsyncExitStack
    ) -> StoredMedia:
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
            uploads.push_async_callback(self._file_storage.delete, storage_key)

        return replace(media, storage_key=storage_key, file_name=path.name, info=info)
