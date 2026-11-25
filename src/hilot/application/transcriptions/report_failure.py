from dataclasses import dataclass

from hilot.domain.interfaces.adapters.transcription_scheduler import TranscriptionReplyScheduler
from hilot.domain.value_objects.transcription import (
    TranscriptionFailure,
    TranscriptionReply,
    TranscriptionRequest,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportTranscriptionFailureDTO:
    request: TranscriptionRequest


class ReportTranscriptionFailure:
    def __init__(self, *, reply_scheduler: TranscriptionReplyScheduler) -> None:
        self._reply_scheduler: TranscriptionReplyScheduler = reply_scheduler

    async def __call__(self, data: ReportTranscriptionFailureDTO) -> None:
        await self._reply_scheduler.schedule_transcription_reply(
            TranscriptionReply(
                source=data.request.source,
                trigger=data.request.trigger,
                outcome=TranscriptionFailure.BUG,
            )
        )
