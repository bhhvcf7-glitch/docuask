import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import User
from app.db.session import database_url
from app.schemas.auth import Credentials, LoginCredentials


def test_both_schemas_strip_and_casefold_email() -> None:
    for schema in (Credentials, LoginCredentials):
        user = schema(email="  Alice@Example.COM  ", password="valid-password-123")
        assert user.email == "alice@example.com"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="PostgreSQL required")
async def test_database_rejects_case_variant_emails() -> None:
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    first = f"{uuid4()}@example.com"
    try:
        async with maker.begin() as session:
            session.add(User(email=first, password_hash="hash"))
        with pytest.raises(IntegrityError) as err:
            async with maker.begin() as session:
                session.add(User(email=first.upper(), password_hash="hash"))
        assert "uq_users_email_lower" in str(err.value)
    finally:
        async with maker.begin() as session:
            await session.execute(text("DELETE FROM users WHERE lower(email) = :mail"), {"mail": first})
        await engine.dispose()
