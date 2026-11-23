from sqlalchemy.engine import URL

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
