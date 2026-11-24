from dataclasses import dataclass
from pathlib import Path

from hilot.domain.errors.watermark import DetectionQuotaExceededError
from hilot.domain.interfaces.adapters.file_storage import FileStorage
from hilot.domain.interfaces.adapters.watermark_detector import WatermarkDetector
from hilot.domain.interfaces.adapters.watermark_scheduler import WatermarkReplyScheduler
from hilot.domain.interfaces.adapters.workspace import Workspace
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
    def __init__(
        self,
        *,
        watermark_detector: WatermarkDetector,
        workspace: Workspace,
        file_storage: FileStorage,
        reply_scheduler: WatermarkReplyScheduler,
    ) -> None:
        self._watermark_detector: WatermarkDetector = watermark_detector
        self._workspace: Workspace = workspace
        self._file_storage: FileStorage = file_storage
        self._reply_scheduler: WatermarkReplyScheduler = reply_scheduler

    async def __call__(self, data: CheckWatermarkDTO) -> None:
        # a failed task isn't retried, so its media goes either way
        try:
            async with self._workspace.create() as directory:
                path: Path = directory / "media"
                await self._file_storage.download(key=data.request.storage_key, path=path)

                outcome: (
                    WatermarkCheck | WatermarkQuotaExceeded
                ) = await self._watermark_detector.detect(
                    path=path, mime_type=data.request.mime_type
                )
        except DetectionQuotaExceededError as error:
            outcome = WatermarkQuotaExceeded(retry_after=error.retry_after)
        finally:
            await self._file_storage.delete(data.request.storage_key)

        await self._reply_scheduler.schedule_reply(
            WatermarkReply(source=data.request.source, outcome=outcome)
        )
