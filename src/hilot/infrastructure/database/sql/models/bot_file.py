from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BotFileModel(Base):
    __tablename__ = "bot_files"

    # the file ids of a bot work only for itself
    bot_id: Mapped[int] = mapped_column(primary_key=True)
    extractor: Mapped[str] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(primary_key=True)

    file_id: Mapped[str]
