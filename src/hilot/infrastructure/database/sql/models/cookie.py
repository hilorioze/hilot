from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CookieModel(Base):
    __tablename__ = "cookies"

    domain: Mapped[str] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(primary_key=True)

    encrypted_value: Mapped[bytes]

    expires: Mapped[int | None]
    include_subdomains: Mapped[bool]
    secure: Mapped[bool]
