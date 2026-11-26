from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CachedTranscriptModel(Base):
    __tablename__ = "cached_transcripts"

    file_unique_id: Mapped[str] = mapped_column(primary_key=True)

    # the speech of other people too, so it's kept encrypted like the credentials
    encrypted_text: Mapped[bytes]

    cached_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
