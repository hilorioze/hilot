from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .cached_watermark_check import CachedWatermarkCheckModel


class TelegramFileHashModel(Base):
    __tablename__ = "telegram_file_hashes"

    file_unique_id: Mapped[str] = mapped_column(primary_key=True)

    # a telegram id leads only to a kept check, so it goes with the check
    content_hash: Mapped[str] = mapped_column(
        ForeignKey(CachedWatermarkCheckModel.content_hash, ondelete="CASCADE"), index=True
    )
