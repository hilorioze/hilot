from datetime import datetime

from sqlalchemy import ARRAY, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DeliveredPartModel(Base):
    __tablename__ = "delivered_parts"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(primary_key=True)

    part: Mapped[int] = mapped_column(primary_key=True)

    message_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))

    delivered_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
