"""add media info of cached files"""

import sqlalchemy as sa
from alembic import op

revision: str = "14e1c2deac19"
down_revision: str | None = "944d8659f57b"


def upgrade() -> None:
    # the cached files have no media info to fill in, so the next delivery sends their stored file or downloads them again
    op.execute("DELETE FROM cached_files")

    op.add_column("cached_files", sa.Column("size", sa.BigInteger(), nullable=False))
    op.add_column("cached_files", sa.Column("container", sa.String(), nullable=False))
    op.add_column("cached_files", sa.Column("video_codec", sa.String(), nullable=True))
    op.add_column("cached_files", sa.Column("audio_codec", sa.String(), nullable=True))
    op.add_column("cached_files", sa.Column("duration", sa.Double(), nullable=True))
    op.add_column("cached_files", sa.Column("width", sa.BigInteger(), nullable=True))
    op.add_column("cached_files", sa.Column("height", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("cached_files", "height")
    op.drop_column("cached_files", "width")
    op.drop_column("cached_files", "duration")
    op.drop_column("cached_files", "audio_codec")
    op.drop_column("cached_files", "video_codec")
    op.drop_column("cached_files", "container")
    op.drop_column("cached_files", "size")
