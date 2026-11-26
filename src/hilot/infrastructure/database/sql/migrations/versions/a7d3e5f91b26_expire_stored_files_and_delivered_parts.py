"""expire the stored files and the delivered parts"""

import sqlalchemy as sa
from alembic import op

revision: str = "a7d3e5f91b26"
down_revision: str | None = "5f2b8d7c1e93"


def upgrade() -> None:
    # the stored files from before expire at once, at worst a media of the last hours is downloaded again
    op.add_column(
        "stored_files", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE stored_files SET expires_at = stored_at")
    op.alter_column("stored_files", "expires_at", nullable=False)
    op.drop_column("stored_files", "stored_at")
    op.create_index(op.f("ix_stored_files_expires_at"), "stored_files", ["expires_at"])

    # the parts from before get a day from now, like a part delivered now
    op.add_column(
        "delivered_parts", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "delivered_parts", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE delivered_parts SET delivered_at = now(), expires_at = now() + interval '1 day'"
    )
    op.alter_column("delivered_parts", "delivered_at", nullable=False)
    op.alter_column("delivered_parts", "expires_at", nullable=False)
    op.create_index(op.f("ix_delivered_parts_expires_at"), "delivered_parts", ["expires_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_delivered_parts_expires_at"), table_name="delivered_parts")
    op.drop_column("delivered_parts", "expires_at")
    op.drop_column("delivered_parts", "delivered_at")

    op.drop_index(op.f("ix_stored_files_expires_at"), table_name="stored_files")
    op.add_column(
        "stored_files",
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("UPDATE stored_files SET stored_at = expires_at")
    op.drop_column("stored_files", "expires_at")
