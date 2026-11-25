from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TelegramFileHashModel(Base):
    __tablename__ = "telegram_file_hashes"

    file_unique_id: Mapped[str] = mapped_column(primary_key=True)

    content_hash: Mapped[str]
