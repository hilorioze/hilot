"""link the posts of the cached files and their authors"""

import sqlalchemy as sa
from alembic import op

revision: str = "88e1a4cda226"
down_revision: str | None = "c81e4f2a9d35"


def upgrade() -> None:
    for table in ("stored_files", "cached_files"):
        op.add_column(table, sa.Column("post_url", sa.String(), nullable=True))
        op.add_column(table, sa.Column("post_author_url", sa.String(), nullable=True))


def downgrade() -> None:
    for table in ("stored_files", "cached_files"):
        op.drop_column(table, "post_author_url")
        op.drop_column(table, "post_url")
