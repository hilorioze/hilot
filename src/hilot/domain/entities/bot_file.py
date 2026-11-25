from dataclasses import dataclass, field

from hilot.domain.value_objects.media import FileId, MediaKey


# a file uploaded by the inline bot, which takes only its own files into rich messages
@dataclass(frozen=True, slots=True, kw_only=True)
class BotFile:
    media_key: MediaKey

    file_id: FileId = field(compare=False)
