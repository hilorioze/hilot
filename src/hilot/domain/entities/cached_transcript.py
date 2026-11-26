from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from hilot.domain.value_objects.media import FileUniqueId
from hilot.domain.value_objects.transcription import Transcript


# the transcript of a telegram file, which the file sent or forwarded again gets without a transcription
@dataclass(frozen=True, slots=True, kw_only=True)
class CachedTranscript:
    # a voice is mostly forwarded within days, and the speech of other people isn't kept longer than its reuse needs
    _LIFETIME: ClassVar[timedelta] = timedelta(weeks=1)

    file_unique_id: FileUniqueId

    transcript: Transcript = field(compare=False)

    cached_at: datetime = field(compare=False)

    def get_expiry(self) -> datetime:
        return self.cached_at + self._LIFETIME
