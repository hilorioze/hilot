from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CachedTranscriptModel(Base):
    __tablename__ = "cached_transcripts"

    file_unique_id: Mapped[str] = mapped_column(primary_key=True)

    text: Mapped[str]
