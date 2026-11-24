import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from hilot.domain.entities.detection_account import DetectionAccount
from hilot.domain.errors.watermark import (
    DetectionAccountRevokedError,
    DetectionQuotaExceededError,
    NoDetectionAccountsError,
)
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.watermark_detector import (
    DetectableMediaMatcher,
    WatermarkDetector,
)
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkReplyScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
from hilot.domain.interfaces.repositories.detection_account import DetectionAccountRepository
from hilot.domain.interfaces.unit_of_work import UnitOfWork
from hilot.domain.value_objects.media import MediaKind
from hilot.domain.value_objects.watermark import (
    WatermarkCheck,
    WatermarkCheckRequest,
    WatermarkQuotaExceeded,
    WatermarkReply,
)


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
        uow: UnitOfWork,
        workspace: Workspace,
        file_storage: FileStorage,
        reply_scheduler: WatermarkReplyScheduler,
    ) -> None:
        self._watermark_detector: WatermarkDetector = watermark_detector
        self._media_matcher: DetectableMediaMatcher = media_matcher
        self._account_repository: DetectionAccountRepository = account_repository
        self._uow: UnitOfWork = uow
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._reply_scheduler: WatermarkReplyScheduler = reply_scheduler

    async def __call__(self, data: CheckWatermarkDTO) -> None:
        # a failed task isn't retried, so its media goes either way
        try:
            async with self._workspace.create() as directory:
                path: Path = directory / "media"
                await self._file_storage.download(key=data.request.storage_key, path=path)

                outcome: WatermarkCheck | WatermarkQuotaExceeded = await self._detect(
                    path=path, mime_type=data.request.mime_type
                )
        except DetectionQuotaExceededError as error:
            outcome = WatermarkQuotaExceeded(retry_after=error.retry_after)
        finally:
            await self._file_storage.delete(data.request.storage_key)

        await self._reply_scheduler.schedule_reply(
            WatermarkReply(source=data.request.source, outcome=outcome)
        )

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
