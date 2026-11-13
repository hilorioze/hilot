from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import BigInteger, DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata: ClassVar[MetaData] = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )

    type_annotation_map: ClassVar[dict[Any, Any]] = {
        # telegram ids and cookie expiry times don't fit into a 32-bit `integer`
        int: BigInteger,
        datetime: DateTime(timezone=True),
    }
