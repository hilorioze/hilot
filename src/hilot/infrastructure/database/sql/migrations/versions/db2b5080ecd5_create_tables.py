"""create tables"""

import sqlalchemy as sa
from alembic import op

revision: str = "db2b5080ecd5"
down_revision: str | None = None


def upgrade() -> None:
    op.create_table(
        "cached_files",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("extractor", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("kind", sa.Enum("PHOTO", "VIDEO", "AUDIO", name="mediakind"), nullable=False),
        sa.Column("file_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "account_id", "extractor", "media_id", name=op.f("pk_cached_files")
        ),
    )
    op.create_table(
        "cookies",
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("expires", sa.BigInteger(), nullable=True),
        sa.Column("include_subdomains", sa.Boolean(), nullable=False),
        sa.Column("secure", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("domain", "path", "name", name=op.f("pk_cookies")),
    )
    op.create_table(
        "delivered_parts",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("part", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "account_id", "chat_id", "message_id", "part", name=op.f("pk_delivered_parts")
        ),
    )
    op.create_table(
        "peers",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_id", sa.BigInteger(), nullable=False),
        sa.Column("access_hash", sa.BigInteger(), nullable=False),
        sa.Column("peer_type", sa.String(), nullable=False),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("account_id", "peer_id", name=op.f("pk_peers")),
    )
    op.create_index(op.f("ix_peers_phone_number"), "peers", ["phone_number"], unique=False)
    op.create_table(
        "stored_files",
        sa.Column("extractor", sa.String(), nullable=False),
        sa.Column("media_id", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("kind", sa.Enum("PHOTO", "VIDEO", "AUDIO", name="mediakind"), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("container", sa.String(), nullable=False),
        sa.Column("video_codec", sa.String(), nullable=True),
        sa.Column("audio_codec", sa.String(), nullable=True),
        sa.Column("duration", sa.Double(), nullable=True),
        sa.Column("width", sa.BigInteger(), nullable=True),
        sa.Column("height", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("performer", sa.String(), nullable=True),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("extractor", "media_id", name=op.f("pk_stored_files")),
    )
    op.create_table(
        "update_states",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("state_id", sa.BigInteger(), nullable=False),
        sa.Column("pts", sa.BigInteger(), nullable=True),
        sa.Column("qts", sa.BigInteger(), nullable=True),
        sa.Column("date", sa.BigInteger(), nullable=True),
        sa.Column("seq", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("account_id", "state_id", name=op.f("pk_update_states")),
    )
    op.create_table(
        "usernames",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "peer_id"],
            ["peers.account_id", "peers.peer_id"],
            name=op.f("fk_usernames_account_id_peers"),
        ),
        sa.PrimaryKeyConstraint("account_id", "peer_id", "username", name=op.f("pk_usernames")),
    )
    op.create_index(
        op.f("ix_usernames_account_id"), "usernames", ["account_id", "username"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_usernames_account_id"), table_name="usernames")
    op.drop_table("usernames")
    op.drop_table("update_states")
    op.drop_index(op.f("ix_peers_phone_number"), table_name="peers")
    op.drop_table("stored_files")
    op.drop_table("peers")
    op.drop_table("delivered_parts")
    op.drop_table("cookies")
    op.drop_table("cached_files")

    # dropping the table leaves its enum type behind
    sa.Enum(name="mediakind").drop(op.get_bind())
