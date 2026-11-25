from dataclasses import dataclass, field

from hilot.domain.value_objects.media import FileUniqueId
from hilot.domain.value_objects.transcription import Transcript


# the transcript of a telegram file, which the file sent or forwarded again gets without a transcription
@dataclass(frozen=True, slots=True, kw_only=True)
class CachedTranscript:
    file_unique_id: FileUniqueId

    transcript: Transcript = field(compare=False)
