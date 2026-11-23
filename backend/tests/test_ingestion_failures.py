import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Document, User
from app.db.session import database_url
from app.services.ingestion import ingest_document
from app.services.recovery import fail_stale_ingestions

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="PostgreSQL required"),
]


class BrokenEmbeddings:
    async def documents(self, passages: list[str]) -> list[list[float]]:
        raise TypeError("unexpected embedding failure")


async def test_unexpected_embedding_error_marks_document_failed(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    engine = create_async_engine(database_url(settings))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    owner, doc_id = uuid4(), uuid4()
    folder = tmp_path / str(owner)
    folder.mkdir()
    path = folder / f"{doc_id}.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(50, 700, "A readable document.")
    pdf.save()
    try:
        async with maker.begin() as session:
            session.add(User(id=owner, email=f"{owner}@example.com", password_hash="hash"))
            await session.flush()
            session.add(Document(
                id=doc_id, user_id=owner, original_name="file.pdf",
                storage_key=f"{owner}/{doc_id}.pdf", media_type="application/pdf",
                size_bytes=path.stat().st_size, sha256="a" * 64, status="queued",
            ))
        await ingest_document(doc_id, owner, settings, embeddings=BrokenEmbeddings())
        async with maker() as session:
            document = await session.get(Document, doc_id)
            assert document.status == "failed"
            assert "unexpected embedding failure" not in document.failure_reason
    finally:
        async with maker.begin() as session:
            await session.execute(delete(User).where(User.id == owner))
        await engine.dispose()


async def test_startup_sweep_only_marks_old_processing_documents() -> None:
    settings = Settings(_env_file=None, stale_processing_minutes=30)
    engine = create_async_engine(database_url(settings))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    owner, old_id, recent_id = uuid4(), uuid4(), uuid4()
    try:
        async with maker.begin() as session:
            session.add(User(id=owner, email=f"{owner}@example.com", password_hash="hash"))
            await session.flush()
            for doc_id, label in ((old_id, "a"), (recent_id, "b")):
                session.add(Document(
                    id=doc_id, user_id=owner, original_name="file.pdf",
                    storage_key=f"{owner}/{doc_id}.pdf", media_type="application/pdf",
                    size_bytes=10, sha256=label * 64, status="processing",
                ))
            await session.flush()
            await session.execute(
                update(Document).where(Document.id == old_id)
                .values(status_changed_at=datetime.now(UTC) - timedelta(hours=2))
            )
        assert await fail_stale_ingestions(settings) >= 1
        async with maker() as session:
            assert (await session.get(Document, old_id)).status == "failed"
            assert (await session.get(Document, recent_id)).status == "processing"
    finally:
        async with maker.begin() as session:
            await session.execute(delete(User).where(User.id == owner))
        await engine.dispose()
