from datetime import UTC, datetime

from hilot.domain.interfaces.repositories.cached_transcript import (
    CachedTranscriptExpiryRepository,
)
from hilot.domain.interfaces.repositories.cached_watermark_check import (
    CachedWatermarkCheckRepository,
)
from hilot.domain.interfaces.repositories.delivered_part import DeliveredPartRepository
from hilot.domain.interfaces.repositories.stored_file import StoredFileRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork


class DeleteExpiredData:
    def __init__(
        self,
        *,
        cached_watermark_check_repository: CachedWatermarkCheckRepository,
        cached_transcript_expiry_repository: CachedTranscriptExpiryRepository,
        stored_file_repository: StoredFileRepository,
        delivered_part_repository: DeliveredPartRepository,
        uow: UnitOfWork,
    ) -> None:
        self._cached_watermark_check_repository: CachedWatermarkCheckRepository = (
            cached_watermark_check_repository
        )
        self._cached_transcript_expiry_repository: CachedTranscriptExpiryRepository = (
            cached_transcript_expiry_repository
        )
        self._stored_file_repository: StoredFileRepository = stored_file_repository
        self._delivered_part_repository: DeliveredPartRepository = delivered_part_repository
        self._uow: UnitOfWork = uow

    async def __call__(self) -> None:
        now: datetime = datetime.now(UTC)

        async with self._uow:
            await self._cached_watermark_check_repository.delete_expired(now)
            await self._cached_transcript_expiry_repository.delete_expired(now)
            await self._stored_file_repository.delete_expired(now)
            await self._delivered_part_repository.delete_expired(now)
