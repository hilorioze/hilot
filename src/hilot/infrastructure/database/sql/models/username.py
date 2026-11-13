from sqlalchemy import ForeignKeyConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .peer import PeerModel


class UsernameModel(Base):
    __tablename__ = "usernames"
    __table_args__ = (
        ForeignKeyConstraint(["account_id", "peer_id"], [PeerModel.account_id, PeerModel.peer_id]),
        Index(None, "account_id", "username"),
    )

    account_id: Mapped[int] = mapped_column(primary_key=True)
    peer_id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(primary_key=True)
