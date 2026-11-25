from dataclasses import dataclass
from pathlib import Path

from hilot.domain.entities.cached_file import CachedFile
from hilot.domain.entities.stored_file import StoredFile
from hilot.domain.errors.extraction import (
    DownloadFailedError,
    NoMediaError,
    TooBigError,
    UnsupportedLinkError,
)
from hilot.domain.interfaces.adapters.delivery_scheduler import DeliveryScheduler
from hilot.domain.interfaces.adapters.disk_space import DiskSpace
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.media_extractor import Extraction, MediaExtractor
from hilot.domain.interfaces.adapters.media_lock import MediaLock
from hilot.domain.interfaces.adapters.media_prober import MediaProber
from hilot.domain.interfaces.adapters.transcode_scheduler import TranscodeScheduler
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkCheckScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.cached_file import CachedFileRepository
from hilot.domain.interfaces.repositories.cookie import CookieRepository
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.cookie import Cookie
from hilot.domain.value_objects.download import (
    DownloadPurpose,
    DownloadRequest,
    DownloadResult,
    Failure,
)
from hilot.domain.value_objects.media import ExtractedMedia, MediaInfo, StorageKey, StoredMedia
from hilot.domain.value_objects.message import Link
from hilot.domain.value_objects.watermark import WatermarkCheckRequest

from .converters import convert_stored_file_to_media, convert_stored_media_to_file


@dataclass(frozen=True, slots=True, kw_only=True)
class DownloadMediaDTO:
    request: DownloadRequest


class DownloadMedia:
    def __init__(
        self,
        *,
        media_extractor: MediaExtractor,
        workspace: Workspace,
        disk_space: DiskSpace,
        media_prober: MediaProber,
        file_storage: FileStorage,
        transcode_scheduler: TranscodeScheduler,
        delivery_scheduler: DeliveryScheduler,
        check_scheduler: WatermarkCheckScheduler,
        cookie_repository: CookieRepository,
        cached_file_repository: CachedFileRepository,
        stored_file_repository: StoredFileRepository,
        media_lock: MediaLock,
        uow: UnitOfWork,
    ) -> None:
        self._media_extractor: MediaExtractor = media_extractor
        self._workspace: Workspace = workspace
        self._disk_space: DiskSpace = disk_space
        self._media_prober: MediaProber = media_prober
        self._file_storage: FileStorage = file_storage
        self._transcode_scheduler: TranscodeScheduler = transcode_scheduler
        self._delivery_scheduler: DeliveryScheduler = delivery_scheduler
        self._check_scheduler: WatermarkCheckScheduler = check_scheduler
        self._cookie_repository: CookieRepository = cookie_repository
        self._cached_file_repository: CachedFileRepository = cached_file_repository
        self._stored_file_repository: StoredFileRepository = stored_file_repository
        self._media_lock: MediaLock = media_lock
        self._uow: UnitOfWork = uow

    async def __call__(self, data: DownloadMediaDTO) -> None:
        items: list[StoredMedia | CachedFile | Failure] = []

        async with self._workspace.create() as directory:
            for link in data.request.links:
                items.extend(
                    await self._download_link(request=data.request, link=link, directory=directory)
                )

        result: DownloadResult = DownloadResult.from_items(request=data.request, items=items)

        if data.request.purpose == DownloadPurpose.WATERMARK_CHECK:
            await self._check_scheduler.schedule_check(WatermarkCheckRequest.from_download(result))
        elif result.needs_transcoding():
            await self._transcode_scheduler.schedule_transcode(result)
        else:
            await self._delivery_scheduler.schedule_delivery(result)

    async def _download_link(
        self, *, request: DownloadRequest, link: Link, directory: Path
    ) -> list[StoredMedia | CachedFile | Failure]:
        async with self._uow:
            cookies: list[Cookie] = await self._cookie_repository.get_all()

        try:
            async with self._media_extractor.extract(
                url=link.url, cookies=cookies, directory=directory, size_limit=request.size_limit
            ) as extraction:
                items: list[StoredMedia | CachedFile | Failure] = [
                    await self._download_entry(
                        request=request, link=link, extraction=extraction, entry=entry
                    )
                    for entry in extraction.entries
                ]
                updated_cookies: list[Cookie] = extraction.cookies
        except UnsupportedLinkError, NoMediaError:
            return []
        except DownloadFailedError as error:
            return [Failure.from_error(link=link, error=error)]

        async with self._uow:
            await self._cookie_repository.delete(
                [cookie for cookie in cookies if cookie not in updated_cookies]
            )
            await self._cookie_repository.save(
                [cookie for cookie in updated_cookies if cookie not in cookies]
            )

        return items

    async def _download_entry(
        self,
        *,
        request: DownloadRequest,
        link: Link,
        extraction: Extraction,
        entry: ExtractedMedia,
    ) -> StoredMedia | CachedFile | Failure:
        if request.reuses_sent_media():
            async with self._uow:
                cached_file: CachedFile | None = await self._cached_file_repository.get(
                    account_id=request.source.account_id, media_key=entry.media_key
                )

            if cached_file is not None:
                return cached_file

        # the accounts that get the same media at once wait for one download of it
        async with self._media_lock.acquire(entry.media_key):
            async with self._uow:
                stored_file: StoredFile | None = await self._stored_file_repository.get(
                    entry.media_key
                )

            # reuse the file another account stored lately if it fits this account's limit, a premium one's may not
            if stored_file is not None and request.can_take(stored_file.info):
                return convert_stored_file_to_media(stored_file=stored_file, link=link)

            # a failed media doesn't stop the rest of the link
            try:
                return await self._store_entry(
                    request=request, link=link, extraction=extraction, entry=entry
                )
            except DownloadFailedError as error:
                return Failure.from_error(link=link, error=error)

    async def _store_entry(
        self,
        *,
        request: DownloadRequest,
        link: Link,
        extraction: Extraction,
        entry: ExtractedMedia,
    ) -> StoredMedia:
        if entry.size is not None and entry.size > request.size_limit:
            raise TooBigError(size=entry.size)

        async with (
            self._disk_space.reserve(entry.size or request.size_limit),
            extraction.download(entry) as path,
        ):
            info: MediaInfo = await self._media_prober.probe(path)

            if not request.can_take(info):
                raise TooBigError(size=info.size)

            storage_key: StorageKey = await self._file_storage.upload(path)

        media: StoredMedia = StoredMedia(
            link=link,
            media_key=entry.media_key,
            storage_key=storage_key,
            file_name=path.name,
            info=info,
            title=entry.title,
            performer=entry.performer,
            post=entry.post,
        )

        # the other accounts and a retry of this download reuse the file until the file storage expires it
        async with self._uow:
            await self._stored_file_repository.save(convert_stored_media_to_file(media))

        return media
