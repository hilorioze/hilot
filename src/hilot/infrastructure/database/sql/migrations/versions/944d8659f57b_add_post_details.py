"""add post details"""

import sqlalchemy as sa
from alembic import op

revision: str = "944d8659f57b"
down_revision: str | None = "71f7ab36e659"


def upgrade() -> None:
    for table in ("stored_files", "cached_files"):
        op.add_column(table, sa.Column("post_title", sa.String(), nullable=True))
        op.add_column(table, sa.Column("post_description", sa.String(), nullable=True))
        op.add_column(table, sa.Column("post_author", sa.String(), nullable=True))


def downgrade() -> None:
    for table in ("stored_files", "cached_files"):
        op.drop_column(table, "post_author")
        op.drop_column(table, "post_description")
        op.drop_column(table, "post_title")
