"""add the cached verdicts of watermark checks"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7c2e9a41d5b3"
down_revision: str | None = "45589ad9fd43"


def upgrade() -> None:
    op.create_table(
        "cached_watermark_checks",
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("check", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("content_hash", name=op.f("pk_cached_watermark_checks")),
    )


def downgrade() -> None:
    op.drop_table("cached_watermark_checks")
