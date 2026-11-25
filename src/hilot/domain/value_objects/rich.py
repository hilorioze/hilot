from dataclasses import dataclass

from .media import FileId, MediaKind
from .text import RichText


@dataclass(frozen=True, slots=True, kw_only=True)
class RichMedia:
    kind: MediaKind
    file_id: FileId


# a message with more room than a plain one: up to 50 media in one message and a long text under them
@dataclass(frozen=True, slots=True, kw_only=True)
class RichMessage:
    media: list[RichMedia]
    text: RichText | None
