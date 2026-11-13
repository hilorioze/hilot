import asyncio

from alembic import context
from sqlalchemy import Connection, NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# the package imports every model, so `Base.metadata` has all the tables
from hilot.infrastructure.database.sql.models import Base


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)

    with context.begin_transaction():
        context.run_migrations()


async def migrate() -> None:
    engine: AsyncEngine = create_async_engine(
        context.config.attributes["database_url"], poolclass=NullPool
    )

    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)

    await engine.dispose()


asyncio.run(migrate())
