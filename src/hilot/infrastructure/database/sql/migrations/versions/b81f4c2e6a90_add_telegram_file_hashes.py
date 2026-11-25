"""add the content hashes of telegram files"""

import sqlalchemy as sa
from alembic import op

revision: str = "b81f4c2e6a90"
down_revision: str | None = "7c2e9a41d5b3"


def upgrade() -> None:
    op.create_table(
        "telegram_file_hashes",
        sa.Column("file_unique_id", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("file_unique_id", name=op.f("pk_telegram_file_hashes")),
    )


def downgrade() -> None:
    op.drop_table("telegram_file_hashes")
