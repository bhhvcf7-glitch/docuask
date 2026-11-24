import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.dependencies import get_session
from app.core.config import Settings, get_settings
from app.db.models import Document
from app.db.repositories import get_document
from app.db.session import database_url
from app.main import app

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requires migrated PostgreSQL and RUN_DB_TESTS=1",
    ),
]

TEST_SETTINGS = Settings(
    _env_file=None,
    jwt_secret=SecretStr("integration-only-secret-must-be-long-enough"),
)


@pytest.fixture
async def api() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            async def test_session() -> AsyncIterator[AsyncSession]:
                yield session

            app.dependency_overrides[get_session] = test_session
            app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
            try:
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    yield client, session
            finally:
                app.dependency_overrides.clear()
                await transaction.rollback()
    await engine.dispose()


async def test_register_login_and_current_user(api) -> None:
    client, _ = api
    email = f"{uuid4()}@example.com"
    created = await client.post("/auth/register", json={
        "email": email.upper(), "password": "a-secure-password-123",
    })
    assert created.status_code == 201
    assert created.json()["email"] == email
    assert "password_hash" not in created.json()
    duplicate = await client.post("/auth/register", json={
        "email": email, "password": "another-secure-password",
    })
    assert duplicate.status_code == 409
    login = await client.post("/auth/login", json={
        "email": email.upper(), "password": "a-secure-password-123",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["id"] == created.json()["id"]


async def test_invalid_credentials_and_missing_token(api) -> None:
    client, _ = api
    email = f"{uuid4()}@example.com"
    created = await client.post("/auth/register", json={
        "email": email, "password": "correct-password-123",
    })
    assert created.status_code == 201
    wrong = await client.post("/auth/login", json={
        "email": email, "password": "wrong-password-123",
    })
    assert wrong.status_code == 401
    unknown = await client.post("/auth/login", json={
        "email": f"{uuid4()}@example.com", "password": "wrong-password",
    })
    assert unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert (await client.get("/auth/me")).status_code == 401
    assert (await client.get("/auth/me", headers={"Authorization": "Bearer broken"})).status_code == 401


async def test_token_identity_cannot_read_another_users_document(api) -> None:
    client, session = api
    alice_email, bob_email = f"{uuid4()}@example.com", f"{uuid4()}@example.com"
    alice = (await client.post("/auth/register", json={
        "email": alice_email, "password": "valid-password-123",
    })).json()
    bob = (await client.post("/auth/register", json={
        "email": bob_email, "password": "valid-password-456",
    })).json()
    doc_id = uuid4()
    session.add(Document(
        id=doc_id, user_id=UUID(alice["id"]), original_name="private.pdf",
        storage_key="private/file.pdf", media_type="application/pdf",
        size_bytes=100, sha256="c" * 64, status="ready",
    ))
    await session.flush()
    bob_token = (await client.post("/auth/login", json={
        "email": bob_email, "password": "valid-password-456",
    })).json()["access_token"]
    profile = await client.get("/auth/me", headers={"Authorization": f"Bearer {bob_token}"})
    assert profile.json()["id"] == bob["id"]
    assert await get_document(session, user_id=UUID(bob["id"]), document_id=doc_id) is None
    assert await get_document(session, user_id=UUID(alice["id"]), document_id=doc_id)


async def test_refresh_rotation_and_replay_revokes_family(api) -> None:
    client, session = api
    email = f"{uuid4()}@example.com"
    password = "valid-password-123"
    assert (await client.post("/auth/register", json={
        "email": email, "password": password,
    })).status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": password})
    raw = login.json()["refresh_token"]
    from app.db.models import RefreshToken
    from app.services.refresh import digest_token
    assert await session.get(RefreshToken, raw) is None
    assert await session.get(RefreshToken, digest_token(raw)) is not None
    rotated = await client.post("/auth/refresh", json={"refresh_token": raw})
    assert rotated.status_code == 200
    replacement = rotated.json()["refresh_token"]
    assert replacement != raw
    assert (await client.post("/auth/refresh", json={"refresh_token": raw})).status_code == 401
    assert (await client.post("/auth/refresh", json={
        "refresh_token": replacement,
    })).status_code == 401
