"""add bot files and the messages of the delivered parts"""

import sqlalchemy as sa
from alembic import op

revision: str = "e44f73d76440"
down_revision: str | None = "14e1c2deac19"


def upgrade() -> None:
    op.create_table(
        "bot_files",
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("extractor", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("bot_id", "extractor", "media_id", name=op.f("pk_bot_files")),
    )

    # the parts delivered before keep no messages, so a command answered again over them names none of their posts
    op.add_column(
        "delivered_parts",
        sa.Column("message_ids", sa.ARRAY(sa.BigInteger()), nullable=False, server_default="{}"),
    )
    op.alter_column("delivered_parts", "message_ids", server_default=None)


def downgrade() -> None:
    op.drop_column("delivered_parts", "message_ids")
    op.drop_table("bot_files")
