import io
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from qdrant_client import AsyncQdrantClient
from reportlab.pdfgen import canvas
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_session
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import database_url
from app.main import app

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1" or os.getenv("RUN_VECTOR_TESTS") != "1",
        reason="Requires PostgreSQL and Qdrant services",
    ),
]


class FixedEmbeddings:
    dimension = 3

    async def documents(self, passages: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in passages]

    async def query(self, question: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class CitingProvider:
    async def stream(self, messages):
        match = re.search(r"\[source:([a-f0-9-]{36})\]", messages[0]["content"])
        assert match is not None
        yield "The annual report records revenue. "
        yield f"[source:{match.group(1)}]"


def sample_pdf() -> bytes:
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(50, 700, "The annual report records revenue.")
    pdf.showPage()
    pdf.save()
    return output.getvalue()


async def register(client: httpx.AsyncClient) -> tuple[str, str]:
    email = f"{uuid4()}@example.com"
    password = "development-password-123"
    created = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    return created.json()["id"], login.json()["access_token"]


async def test_upload_to_cited_sse_answer_and_cross_user_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        _env_file=None,
        storage_dir=tmp_path,
        qdrant_collection=f"smoke_{uuid4().hex}",
        jwt_secret=SecretStr("integration-only-secret-must-be-long-enough"),
        qa_min_score=0.1,
    )
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    owners = []

    async def db_session() -> AsyncIterator:
        async with sessions() as session:
            yield session

    monkeypatch.setattr("app.services.ingestion.E5Embeddings", FixedEmbeddings)
    monkeypatch.setattr("app.services.search.E5Embeddings", FixedEmbeddings)
    monkeypatch.setattr("app.api.routes.qa.make_provider", lambda value: CitingProvider())
    app.dependency_overrides[get_session] = db_session
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            owner_a, token_a = await register(client)
            owners.append(UUID(owner_a))
            owner_b, token_b = await register(client)
            owners.append(UUID(owner_b))
            a = {"Authorization": f"Bearer {token_a}"}
            b = {"Authorization": f"Bearer {token_b}"}

            uploaded = await client.post(
                "/documents", headers=a,
                files={"file": ("report.pdf", sample_pdf(), "application/pdf")},
            )
            assert uploaded.status_code == 201, uploaded.text
            doc_id = uploaded.json()["id"]
            status = await client.get(f"/documents/{doc_id}", headers=a)
            assert status.status_code == 200
            assert status.json()["status"] == "ready"

            retrieved = await client.post(
                "/search", headers=a, json={"question": "What is the revenue?"}
            )
            assert retrieved.status_code == 200, retrieved.text
            assert len(retrieved.json()) == 1
            chunk = retrieved.json()[0]
            assert chunk["page_number"] == 1

            answer = await client.post(
                "/qa/ask", headers=a,
                json={"question": "What does the report record?"},
            )
            assert answer.status_code == 200
            assert "event: token" in answer.text
            assert "event: citations" in answer.text
            assert "event: done" in answer.text
            assert chunk["chunk_id"] in answer.text
            assert '"page_number": 1' in answer.text

            assert (await client.get(f"/documents/{doc_id}", headers=b)).status_code == 404
            other = await client.post(
                "/search", headers=b, json={"question": "revenue"}
            )
            assert other.status_code == 200
            assert other.json() == []
            refused = await client.post(
                "/qa/ask", headers=b, json={"question": "revenue"}
            )
            assert refused.status_code == 200
            assert "event: refusal" in refused.text
            assert "event: token" not in refused.text
    finally:
        app.dependency_overrides.clear()
        try:
            async with sessions.begin() as session:
                await session.execute(delete(User).where(User.id.in_(owners)))
            if await qdrant.collection_exists(settings.qdrant_collection):
                await qdrant.delete_collection(settings.qdrant_collection)
        finally:
            await qdrant.close()
            await engine.dispose()
