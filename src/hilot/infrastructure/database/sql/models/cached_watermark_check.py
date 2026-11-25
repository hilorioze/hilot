from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CachedWatermarkCheckModel(Base):
    __tablename__ = "cached_watermark_checks"

    content_hash: Mapped[str] = mapped_column(primary_key=True)

    # a verdict nests its segments, and nothing queries into it
    check: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checked_at: Mapped[datetime]
