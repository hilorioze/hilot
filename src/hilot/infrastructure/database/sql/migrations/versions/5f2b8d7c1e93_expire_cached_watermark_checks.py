"""expire the cached watermark checks with the telegram ids of their files"""

import sqlalchemy as sa
from alembic import op

revision: str = "5f2b8d7c1e93"
down_revision: str | None = "3d9a6e1f0c47"


def upgrade() -> None:
    op.add_column(
        "cached_watermark_checks",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_cached_watermark_checks_expires_at"),
        "cached_watermark_checks",
        ["expires_at"],
    )

    # only a found watermark never expires
    op.execute(
        """
        UPDATE cached_watermark_checks
        SET expires_at = checked_at + interval '1 day'
        WHERE "check" ->> 'verdict' <> 'detected'
        """
    )

    # a telegram id saved before its check was undetermined or failed leads nowhere
    op.execute(
        """
        DELETE FROM telegram_file_hashes
        WHERE content_hash NOT IN (SELECT content_hash FROM cached_watermark_checks)
        """
    )

    op.create_index(
        op.f("ix_telegram_file_hashes_content_hash"), "telegram_file_hashes", ["content_hash"]
    )
    op.create_foreign_key(
        op.f("fk_telegram_file_hashes_content_hash_cached_watermark_checks"),
        "telegram_file_hashes",
        "cached_watermark_checks",
        ["content_hash"],
        ["content_hash"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_telegram_file_hashes_content_hash_cached_watermark_checks"),
        "telegram_file_hashes",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_telegram_file_hashes_content_hash"), table_name="telegram_file_hashes")

    op.drop_index(
        op.f("ix_cached_watermark_checks_expires_at"), table_name="cached_watermark_checks"
    )
    op.drop_column("cached_watermark_checks", "expires_at")
