"""create detection accounts"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "71f7ab36e659"
down_revision: str | None = "db2b5080ecd5"


def upgrade() -> None:
    op.create_table(
        "detection_accounts",
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.LargeBinary(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("uid", name=op.f("pk_detection_accounts")),
    )
    op.create_table(
        "detection_quotas",
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column(
            "kind",
            # the type exists since the first migration
            postgresql.ENUM("PHOTO", "VIDEO", "AUDIO", name="mediakind", create_type=False),
            nullable=False,
        ),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["uid"],
            ["detection_accounts.uid"],
            name=op.f("fk_detection_quotas_uid_detection_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("uid", "kind", name=op.f("pk_detection_quotas")),
    )


def downgrade() -> None:
    op.drop_table("detection_quotas")
    op.drop_table("detection_accounts")
