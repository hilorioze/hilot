from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, NewType

from .message import Link
from .text import RichText

FileId = NewType("FileId", str)
StorageKey = NewType("StorageKey", str)


class MediaKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaKey:
    extractor: str
    media_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MediaInfo:
    _PHOTO_CODECS: ClassVar[set[str]] = {"mjpeg", "png"}
    _VIDEO_AUDIO_CODECS: ClassVar[set[str | None]] = {"aac", "mp3", None}

    kind: MediaKind
    size: int

    container: str
    video_codec: str | None
    audio_codec: str | None

    duration: float | None
    width: int | None
    height: int | None

    # telegram plays inline only h264 videos in mp4 and mp3 or aac audio, and takes photos as jpeg or png
    def needs_transcoding(self) -> bool:
        formats: list[str] = self.container.split(",")

        match self.kind:
            case MediaKind.PHOTO:
                return self.video_codec not in self._PHOTO_CODECS
            case MediaKind.VIDEO:
                return (
                    "mp4" not in formats
                    or self.video_codec != "h264"
                    or self.audio_codec not in self._VIDEO_AUDIO_CODECS
                )
            case MediaKind.AUDIO:
                return not (
                    ("mp3" in formats and self.audio_codec == "mp3")
                    or ("m4a" in formats and self.audio_codec == "aac")
                )

    # transcoding can still shrink it under the limit
    def can_fit(self, size_limit: int) -> bool:
        return self.size <= size_limit or self.needs_transcoding()


# what the site tells about the post of a media, as much as it has
@dataclass(frozen=True, slots=True, kw_only=True)
class PostDetails:
    title: str | None
    description: str | None
    author: str | None


# what goes out to the chat with each file
@dataclass(frozen=True, slots=True, kw_only=True)
class OutgoingMedia:
    file_id: FileId
    caption: RichText | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AttachedMedia:
    file_id: FileId

    mime_type: str
    size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractedMedia:
    media_key: MediaKey
    size: int | None

    title: str | None
    performer: str | None

    post: PostDetails


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredMedia:
    link: Link
    media_key: MediaKey

    storage_key: StorageKey
    file_name: str
    info: MediaInfo

    title: str | None
    performer: str | None

    post: PostDetails

    @property
    def kind(self) -> MediaKind:
        return self.info.kind
