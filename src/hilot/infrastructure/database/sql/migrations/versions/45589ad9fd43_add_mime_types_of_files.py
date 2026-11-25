"""add the mime types of the files"""

import mimetypes

import sqlalchemy as sa
from alembic import op

revision: str = "45589ad9fd43"
down_revision: str | None = "e44f73d76440"

_UNKNOWN_TYPE: str = "application/octet-stream"


def upgrade() -> None:
    # only a watermark check reads the type, and it checks stored files only, so the cached files, which keep no file name, stay unknown
    for table in ("cached_files", "stored_files"):
        op.add_column(
            table,
            sa.Column("mime_type", sa.String(), nullable=False, server_default=_UNKNOWN_TYPE),
        )
        op.alter_column(table, "mime_type", server_default=None)

    stored_files: sa.TableClause = sa.table(
        "stored_files",
        sa.column("extractor"),
        sa.column("media_id"),
        sa.column("file_name"),
        sa.column("mime_type"),
    )
    connection: sa.Connection = op.get_bind()

    for extractor, media_id, file_name in connection.execute(
        sa.select(stored_files.c.extractor, stored_files.c.media_id, stored_files.c.file_name)
    ):
        mime_type: str | None = mimetypes.guess_file_type(file_name)[0]

        if mime_type is not None:
            connection.execute(
                sa.update(stored_files)
                .where(stored_files.c.extractor == extractor, stored_files.c.media_id == media_id)
                .values(mime_type=mime_type)
            )


def downgrade() -> None:
    op.drop_column("stored_files", "mime_type")
    op.drop_column("cached_files", "mime_type")
