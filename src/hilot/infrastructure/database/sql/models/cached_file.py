from sqlalchemy.orm import Mapped, mapped_column

from hilot.domain.value_objects.media import MediaKind

from .base import Base


class CachedFileModel(Base):
    __tablename__ = "cached_files"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    extractor: Mapped[str] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(primary_key=True)

    file_id: Mapped[str]

    kind: Mapped[MediaKind]
    size: Mapped[int]
    mime_type: Mapped[str]
    container: Mapped[str]
    video_codec: Mapped[str | None]
    audio_codec: Mapped[str | None]
    duration: Mapped[float | None]
    width: Mapped[int | None]
    height: Mapped[int | None]

    chat_id: Mapped[int]
    message_id: Mapped[int]

    post_title: Mapped[str | None]
    post_description: Mapped[str | None]
    post_author: Mapped[str | None]
