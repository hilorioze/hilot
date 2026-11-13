from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class UpdateStateModel(Base):
    __tablename__ = "update_states"

    account_id: Mapped[int] = mapped_column(primary_key=True)

    # 0 for the account's common state, a channel id for the channel's own pts
    state_id: Mapped[int] = mapped_column(primary_key=True)

    pts: Mapped[int | None]
    qts: Mapped[int | None]
    date: Mapped[int | None]
    seq: Mapped[int | None]
