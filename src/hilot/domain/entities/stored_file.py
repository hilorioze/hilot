from dataclasses import dataclass, field

from hilot.domain.value_objects.media import MediaInfo, MediaKey, StorageKey


# a file in the file storage that any account can send
@dataclass(frozen=True, slots=True, kw_only=True)
class StoredFile:
    media_key: MediaKey

    storage_key: StorageKey = field(compare=False)
    file_name: str = field(compare=False)
    info: MediaInfo = field(compare=False)

    title: str | None = field(compare=False)
    performer: str | None = field(compare=False)
