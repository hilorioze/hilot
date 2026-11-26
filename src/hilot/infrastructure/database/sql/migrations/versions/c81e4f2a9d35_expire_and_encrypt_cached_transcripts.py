"""expire and encrypt the cached transcripts"""

import sqlalchemy as sa
from alembic import op

revision: str = "c81e4f2a9d35"
down_revision: str | None = "a7d3e5f91b26"


def upgrade() -> None:
    # the migration has no keys to encrypt the transcripts from before, and a cache loses nothing by it
    op.execute("DELETE FROM cached_transcripts")

    op.drop_column("cached_transcripts", "text")
    op.add_column(
        "cached_transcripts", sa.Column("encrypted_text", sa.LargeBinary(), nullable=False)
    )
    op.add_column(
        "cached_transcripts",
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "cached_transcripts",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_cached_transcripts_expires_at"), "cached_transcripts", ["expires_at"])


def downgrade() -> None:
    op.execute("DELETE FROM cached_transcripts")

    op.drop_index(op.f("ix_cached_transcripts_expires_at"), table_name="cached_transcripts")
    op.drop_column("cached_transcripts", "expires_at")
    op.drop_column("cached_transcripts", "cached_at")
    op.drop_column("cached_transcripts", "encrypted_text")
    op.add_column("cached_transcripts", sa.Column("text", sa.String(), nullable=False))
