from typing import Protocol

from hilot.domain.value_objects.transcription import TranscriptionReply, TranscriptionRequest


class TranscriptionScheduler(Protocol):
    async def schedule_transcription(self, request: TranscriptionRequest) -> None: ...


class TranscriptionReplyScheduler(Protocol):
    async def schedule_transcription_reply(self, reply: TranscriptionReply) -> None: ...
