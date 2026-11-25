from typing import Protocol

from hilot.domain.value_objects.transcription import (
    TranscriptionFailure,
    TranscriptionQuotaExceeded,
)


class TranscriptionFormatter(Protocol):
    def format_failure(
        self, outcome: TranscriptionQuotaExceeded | TranscriptionFailure
    ) -> str: ...
