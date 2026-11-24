from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from hilot.domain.value_objects.media import MediaKind

from .base import Base


class DetectionAccountModel(Base):
    __tablename__ = "detection_accounts"

    uid: Mapped[str] = mapped_column(primary_key=True)

    encrypted_refresh_token: Mapped[bytes]

    used_at: Mapped[datetime | None]


class DetectionQuotaModel(Base):
    __tablename__ = "detection_quotas"

    uid: Mapped[str] = mapped_column(
        ForeignKey(DetectionAccountModel.uid, ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[MediaKind] = mapped_column(primary_key=True)

    resets_at: Mapped[datetime]
