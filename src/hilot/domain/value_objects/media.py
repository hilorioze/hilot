from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, NewType

from .message import Link

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


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractedMedia:
    media_key: MediaKey
    size: int | None

    title: str | None
    performer: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredMedia:
    link: Link
    media_key: MediaKey

    storage_key: StorageKey
    file_name: str
    info: MediaInfo

    title: str | None
    performer: str | None

    @property
    def kind(self) -> MediaKind:
        return self.info.kind
