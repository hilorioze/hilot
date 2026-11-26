from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from hilot.domain.value_objects.media import MediaKind

from .base import Base


class StoredFileModel(Base):
    __tablename__ = "stored_files"

    extractor: Mapped[str] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(primary_key=True)

    storage_key: Mapped[str]
    file_name: Mapped[str]

    kind: Mapped[MediaKind]
    size: Mapped[int]
    mime_type: Mapped[str]
    container: Mapped[str]
    video_codec: Mapped[str | None]
    audio_codec: Mapped[str | None]
    duration: Mapped[float | None]
    width: Mapped[int | None]
    height: Mapped[int | None]

    title: Mapped[str | None]
    performer: Mapped[str | None]

    post_title: Mapped[str | None]
    post_description: Mapped[str | None]
    post_author: Mapped[str | None]

    # the other accounts reuse the file until then, a bit before the file storage expires it
    expires_at: Mapped[datetime] = mapped_column(index=True)
