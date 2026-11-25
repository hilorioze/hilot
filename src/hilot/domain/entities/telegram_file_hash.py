from dataclasses import dataclass, field

from hilot.domain.value_objects.media import ContentHash, FileUniqueId


# the content of a telegram file, known before downloading it again
@dataclass(frozen=True, slots=True, kw_only=True)
class TelegramFileHash:
    file_unique_id: FileUniqueId

    content_hash: ContentHash = field(compare=False)
