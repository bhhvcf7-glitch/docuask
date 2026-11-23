import os
from pathlib import Path
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import database_url
from app.services.ingestion import ingest_document

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Requires migrated PostgreSQL and RUN_DB_TESTS=1",
    ),
]


async def test_background_ingestion_writes_page_numbered_chunks(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner = uuid4()
    document_id = uuid4()
    folder = tmp_path / str(owner)
    folder.mkdir()
    path = folder / f"{document_id}.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(50, 700, "First page of the annual report.")
    pdf.showPage()
    pdf.drawString(50, 700, "Second page contains the total revenue.")
    pdf.save()

    try:
        async with sessions.begin() as session:
            session.add(User(id=owner, email=f"{owner}@example.com", password_hash="hash"))
            await session.flush()
            session.add(Document(
                id=document_id, user_id=owner,
                original_name="report.pdf", storage_key=f"{owner}/{document_id}.pdf",
                media_type="application/pdf", size_bytes=path.stat().st_size,
                sha256="c" * 64, status="queued",
            ))

        await ingest_document(document_id, owner, settings)

        async with sessions() as session:
            doc = await session.get(Document, document_id)
            pieces = list((await session.scalars(
                select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
            )).all())
            assert doc is not None
            assert doc.status == "ready"
            assert [(chunk.ordinal, chunk.page_number) for chunk in pieces] == [(0, 1), (1, 2)]
            assert "annual report" in pieces[0].original_text
            assert "total revenue" in pieces[1].normalized_text

        await ingest_document(document_id, owner, settings)
        async with sessions() as session:
            count = list((await session.scalars(
                select(Chunk).where(Chunk.document_id == document_id)
            )).all())
            assert len(count) == 2
    finally:
        async with sessions.begin() as session:
            await session.execute(delete(User).where(User.id == owner))
        await engine.dispose()


async def test_scanned_pdf_is_marked_failed_instead_of_ready(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, document_id = uuid4(), uuid4()
    folder = tmp_path / str(owner)
    folder.mkdir()
    path = folder / f"{document_id}.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.showPage()
    pdf.save()

    try:
        async with sessions.begin() as session:
            session.add(User(id=owner, email=f"{owner}@example.com", password_hash="hash"))
            session.add(Document(
                id=document_id, user_id=owner,
                original_name="scanned.pdf", storage_key=f"{owner}/{document_id}.pdf",
                media_type="application/pdf", size_bytes=path.stat().st_size,
                sha256="d" * 64, status="queued",
            ))

        await ingest_document(document_id, owner, settings)
        async with sessions() as session:
            doc = await session.get(Document, document_id)
            assert doc is not None
            assert doc.status == "failed"
            assert "OCR" in (doc.failure_reason or "")
    finally:
        async with sessions.begin() as session:
            await session.execute(delete(User).where(User.id == owner))
        await engine.dispose()
