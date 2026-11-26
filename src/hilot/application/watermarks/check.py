import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from hilot.domain.entities.cached_watermark_check import CachedWatermarkCheck
from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.entities.telegram_file_hash import TelegramFileHash
from hilot.domain.errors.watermark import (
    DetectionAccountRevokedError,
    DetectionQuotaExceededError,
    NoDetectionAccountsError,
)
from hilot.domain.interfaces.adapters.file_hasher import FileHasher
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.watermark_detector import (
    DetectableMediaMatcher,
    WatermarkDetector,
)
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkReplyScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.cached_watermark_check import (
    CachedWatermarkCheckRepository,
)
from hilot.domain.interfaces.repositories.detection_account import DetectionAccountRepository
from hilot.domain.interfaces.repositories.telegram_file_hash import TelegramFileHashRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.media import ContentHash, FileUniqueId, MediaKind
from hilot.domain.value_objects.watermark import (
    WatermarkCheck,
    WatermarkCheckRequest,
    WatermarkFailure,
    WatermarkQuotaExceeded,
    WatermarkReply,
    WatermarkResult,
    WatermarkTarget,
    WatermarkVerdict,
)

from .media import find_media_failure


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckWatermarkDTO:
    request: WatermarkCheckRequest


class CheckWatermark:
    # a quota resets daily, so a check waits only for the one about to reset
    _MAX_WAIT: ClassVar[timedelta] = timedelta(minutes=1)

    def __init__(
        self,
        *,
        watermark_detector: WatermarkDetector,
        media_matcher: DetectableMediaMatcher,
        account_repository: DetectionAccountRepository,
        cached_watermark_check_repository: CachedWatermarkCheckRepository,
        telegram_file_hash_repository: TelegramFileHashRepository,
        uow: UnitOfWork,
        workspace: Workspace,
        file_storage: FileStorage,
        file_hasher: FileHasher,
        reply_scheduler: WatermarkReplyScheduler,
    ) -> None:
        self._watermark_detector: WatermarkDetector = watermark_detector
        self._media_matcher: DetectableMediaMatcher = media_matcher
        self._account_repository: DetectionAccountRepository = account_repository
        self._cached_watermark_check_repository: CachedWatermarkCheckRepository = (
            cached_watermark_check_repository
        )
        self._telegram_file_hash_repository: TelegramFileHashRepository = (
            telegram_file_hash_repository
        )
        self._uow: UnitOfWork = uow
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._file_hasher: FileHasher = file_hasher
        self._reply_scheduler: WatermarkReplyScheduler = reply_scheduler

    async def __call__(self, data: CheckWatermarkDTO) -> None:
        results: list[WatermarkResult] = [
            item
            if isinstance(item, WatermarkResult)
            else WatermarkResult(label=item.label, outcome=await self._check_target(item))
            for item in data.request.media
        ]

        await self._reply_scheduler.schedule_reply(
            WatermarkReply(source=data.request.source, results=results)
        )

    async def _check_target(
        self, target: WatermarkTarget
    ) -> WatermarkCheck | WatermarkQuotaExceeded | WatermarkFailure:
        # a failed task isn't retried, so an attached media goes either way
        try:
            failure: WatermarkFailure | None = find_media_failure(
                media_matcher=self._media_matcher, mime_type=target.mime_type, size=target.size
            )

            if failure is not None:
                return failure

            async with self._workspace.create() as directory:
                path: Path = directory / "media"
                await self._file_storage.download(key=target.storage_key, path=path)

                return await self._check_file(
                    path=path, mime_type=target.mime_type, file_unique_id=target.file_unique_id
                )
        except DetectionQuotaExceededError as error:
            return WatermarkQuotaExceeded(retry_after=error.retry_after)
        finally:
            if not target.is_shared:
                await self._file_storage.delete(target.storage_key)

    # the same content, forwarded or sent again by a link, gets its verdict from before
    async def _check_file(
        self, *, path: Path, mime_type: str, file_unique_id: FileUniqueId | None
    ) -> WatermarkCheck:
        content_hash: ContentHash = await self._file_hasher.hash_file(path)

        async with self._uow:
            cached_watermark_check: (
                CachedWatermarkCheck | None
            ) = await self._cached_watermark_check_repository.get(content_hash)

        if cached_watermark_check is None or not cached_watermark_check.is_fresh(
            datetime.now(UTC)
        ):
            check: WatermarkCheck = await self._detect(path=path, mime_type=mime_type)

            # an undetermined verdict is what improvements of the detector fix, so it isn't kept
            if check.verdict == WatermarkVerdict.UNDETERMINED:
                return check

            cached_watermark_check = CachedWatermarkCheck(
                content_hash=content_hash, check=check, checked_at=datetime.now(UTC)
            )

            async with self._uow:
                await self._cached_watermark_check_repository.save(cached_watermark_check)

        # the bot finds the verdict of the same telegram file sent again without downloading it
        if file_unique_id is not None:
            async with self._uow:
                await self._telegram_file_hash_repository.save(
                    TelegramFileHash(file_unique_id=file_unique_id, content_hash=content_hash)
                )

        return cached_watermark_check.check

    async def _detect(self, *, path: Path, mime_type: str) -> WatermarkCheck:
        kind: MediaKind = self._media_matcher.get_kind(mime_type)

        while True:
            account: DetectionAccount = await self._take_account(kind)

            try:
                return await self._watermark_detector.detect(
                    account=account, path=path, mime_type=mime_type
                )
            except DetectionQuotaExceededError as error:
                account.quota_resets[kind] = datetime.now(UTC) + error.retry_after

                async with self._uow:
                    await self._account_repository.save(account)
            except DetectionAccountRevokedError:
                async with self._uow:
                    await self._account_repository.delete(account)

    async def _take_account(self, kind: MediaKind) -> DetectionAccount:
        while True:
            async with self._uow:
                accounts: list[DetectionAccount] = await self._account_repository.get_all()
                now: datetime = datetime.now(UTC)

                if not accounts:
                    raise NoDetectionAccountsError

                available: list[DetectionAccount] = [
                    account for account in accounts if account.has_quota(kind=kind, now=now)
                ]

                if available:
                    account: DetectionAccount = min(
                        available,
                        key=lambda account: account.used_at or datetime.min.replace(tzinfo=UTC),
                    )
                    account.used_at = now
                    await self._account_repository.save(account)

                    return account

            wait: timedelta = min(account.quota_resets[kind] for account in accounts) - now

            if wait > self._MAX_WAIT:
                raise DetectionQuotaExceededError(wait)

            await asyncio.sleep(wait.total_seconds())
