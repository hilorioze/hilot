"""add the cached transcripts of telegram files"""

import sqlalchemy as sa
from alembic import op

revision: str = "3d9a6e1f0c47"
down_revision: str | None = "b81f4c2e6a90"


def upgrade() -> None:
    op.create_table(
        "cached_transcripts",
        sa.Column("file_unique_id", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("file_unique_id", name=op.f("pk_cached_transcripts")),
    )


def downgrade() -> None:
    op.drop_table("cached_transcripts")
