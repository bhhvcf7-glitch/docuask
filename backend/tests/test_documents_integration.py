import io
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from pypdf import PdfWriter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.dependencies import get_session
from app.core.config import Settings, get_settings
from app.db.session import database_url
from app.main import app

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requires migrated PostgreSQL and RUN_DB_TESTS=1",
    ),
]


@pytest.fixture
async def api(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, Path]]:
    settings = Settings(
        _env_file=None,
        jwt_secret=SecretStr("integration-only-secret-must-be-long-enough"),
        storage_dir=tmp_path,
        max_upload_bytes=1024 * 1024,
    )
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint"
                ) as session:
                    async def test_session() -> AsyncIterator[AsyncSession]:
                        yield session

                    app.dependency_overrides[get_session] = test_session
                    app.dependency_overrides[get_settings] = lambda: settings
                    try:
                        async with httpx.AsyncClient(
                            transport=httpx.ASGITransport(app=app),
                            base_url="http://test",
                        ) as client:
                            yield client, tmp_path
                    finally:
                        app.dependency_overrides.clear()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def valid_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


async def auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    email = f"{uuid4()}@example.com"
    password = "test-password-12345"
    registered = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert registered.status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def send_pdf(
    client: httpx.AsyncClient, headers: dict[str, str],
    content: bytes, filename: str = "report.pdf", mime: str = "application/pdf",
) -> httpx.Response:
    return await client.post(
        "/documents", headers=headers,
        files={"file": (filename, content, mime)},
    )


async def test_upload_persists_hash_and_scopes_document_listing(api) -> None:
    client, storage = api
    alice = await auth_headers(client)
    bob = await auth_headers(client)
    pdf = valid_pdf()
    uploaded = await send_pdf(client, alice, pdf, filename="../../private.pdf")
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["original_name"] == "private.pdf"
    assert document["size_bytes"] == len(pdf)
    assert document["status"] == "queued"
    assert len(document["sha256"]) == 64

    listing = await client.get("/documents", headers=alice)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [document["id"]]
    assert (await client.get(f"/documents/{document['id']}", headers=alice)).status_code == 200

    assert (await client.get("/documents", headers=bob)).json() == []
    assert (await client.get(f"/documents/{document['id']}", headers=bob)).status_code == 404
    assert (await client.get("/documents")).status_code == 401
    assert (await send_pdf(client, {}, pdf)).status_code == 401

    saved = list(storage.rglob("*.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == pdf
    assert saved[0].name == f"{document['id']}.pdf"
    assert list(storage.rglob("*.upload")) == []


async def test_same_user_duplicate_conflicts_but_other_user_can_upload(api) -> None:
    client, storage = api
    alice = await auth_headers(client)
    bob = await auth_headers(client)
    pdf = valid_pdf()

    first = await send_pdf(client, alice, pdf)
    assert first.status_code == 201
    second = await send_pdf(client, alice, pdf)
    assert second.status_code == 409
    assert second.json()["detail"] == "Document already uploaded"
    other = await send_pdf(client, bob, pdf)
    assert other.status_code == 201
    assert other.json()["id"] != first.json()["id"]
    assert len(list(storage.rglob("*.pdf"))) == 2
    assert list(storage.rglob("*.upload")) == []


@pytest.mark.parametrize(
    ("filename", "content", "mime", "expected"),
    [
        ("report.txt", b"%PDF-1.7\n%%EOF", "application/pdf", 422),
        ("report.pdf", b"not a PDF", "application/pdf", 422),
        ("report.pdf", b"%PDF-1.7\n%%EOF", "application/pdf", 422),
        ("report.pdf", b"%PDF-1.7\n%%EOF", "text/plain", 422),
        ("report.pdf", b"", "application/pdf", 422),
    ],
)
async def test_invalid_uploads_leave_no_files(
    api, filename: str, content: bytes, mime: str, expected: int,
) -> None:
    client, storage = api
    headers = await auth_headers(client)
    uploaded = await send_pdf(client, headers, content, filename, mime)
    assert uploaded.status_code == expected
    assert list(storage.rglob("*.pdf")) == []
    assert list(storage.rglob("*.upload")) == []
    assert (await client.get("/documents", headers=headers)).json() == []


async def test_upload_size_limit_is_enforced_during_streaming(api) -> None:
    client, storage = api
    headers = await auth_headers(client)
    limited = Settings(
        _env_file=None, jwt_secret=SecretStr("integration-only-secret-must-be-long-enough"),
        storage_dir=storage, max_upload_bytes=128,
    )
    app.dependency_overrides[get_settings] = lambda: limited
    response = await send_pdf(client, headers, valid_pdf())

    assert response.status_code == 413
    assert list(storage.rglob("*.pdf")) == []
    assert list(storage.rglob("*.upload")) == []


async def test_document_id_must_be_a_uuid(api) -> None:
    client, _ = api
    headers = await auth_headers(client)
    response = await client.get("/documents/not-a-uuid", headers=headers)
    assert response.status_code == 422
