from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


def database_url(settings: Settings) -> URL:
    if settings.postgres_password is None:
        raise ValueError("POSTGRES_PASSWORD is required for database access")
    return URL.create(
        "postgresql+asyncpg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def make_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url(settings), pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)
