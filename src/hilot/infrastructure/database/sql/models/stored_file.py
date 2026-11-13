from datetime import datetime

from sqlalchemy import func
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
    container: Mapped[str]
    video_codec: Mapped[str | None]
    audio_codec: Mapped[str | None]
    duration: Mapped[float | None]
    width: Mapped[int | None]
    height: Mapped[int | None]

    title: Mapped[str | None]
    performer: Mapped[str | None]

    stored_at: Mapped[datetime] = mapped_column(server_default=func.now())
