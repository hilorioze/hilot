from sqlalchemy.orm import Mapped, mapped_column

from hilot.domain.value_objects.media import MediaKind

from .base import Base


class CachedFileModel(Base):
    __tablename__ = "cached_files"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    extractor: Mapped[str] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(primary_key=True)

    kind: Mapped[MediaKind]
    file_id: Mapped[str]

    chat_id: Mapped[int]
    message_id: Mapped[int]

    post_title: Mapped[str | None]
    post_description: Mapped[str | None]
    post_author: Mapped[str | None]
