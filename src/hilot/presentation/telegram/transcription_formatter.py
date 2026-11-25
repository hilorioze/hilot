from typing import ClassVar, override

from hilot.domain.interfaces.adapters.transcription_formatter import TranscriptionFormatter
from hilot.domain.value_objects.transcription import (
    TranscriptionFailure,
    TranscriptionQuotaExceeded,
)

from .units import format_wait


class ChatTranscriptionFormatter(TranscriptionFormatter):
    _FAILURE_TEXTS: ClassVar[dict[TranscriptionFailure, str]] = {
        TranscriptionFailure.NO_MEDIA: "nothing to transcribe, reply to a voice, audio or video",
        TranscriptionFailure.NO_SPEECH: "no speech",
        TranscriptionFailure.TOO_LONG: "too long to transcribe",
        TranscriptionFailure.BUG: "transcription failed",
    }

    @override
    def format_failure(self, outcome: TranscriptionQuotaExceeded | TranscriptionFailure) -> str:
        if isinstance(outcome, TranscriptionFailure):
            return self._FAILURE_TEXTS[outcome]

        return f"transcription quota reached, try again in {format_wait(outcome.retry_after)}"
