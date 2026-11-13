from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PeerModel(Base):
    __tablename__ = "peers"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[int] = mapped_column(primary_key=True)

    access_hash: Mapped[int]
    peer_type: Mapped[str]
    phone_number: Mapped[str | None] = mapped_column(index=True)

    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
