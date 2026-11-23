import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import database_url
from app.services import document_lifecycle as lifecycle

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="PostgreSQL required"),
]


async def test_retry_and_delete_enforce_owner_and_remove_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(_env_file=None, storage_dir=tmp_path)
    engine = create_async_engine(database_url(settings))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    alice, bob, doc_id = uuid4(), uuid4(), uuid4()
    folder = tmp_path / str(alice)
    folder.mkdir()
    pdf = folder / f"{doc_id}.pdf"
    pdf.write_bytes(b"%PDF-test")
    cleaned = []

    async def remove_vectors(settings, user_id, document_id):
        cleaned.append((user_id, document_id))

    monkeypatch.setattr(lifecycle, "remove_document_vectors", remove_vectors)
    try:
        async with maker.begin() as session:
            session.add_all([
                User(id=alice, email=f"{alice}@example.com", password_hash="hash"),
                User(id=bob, email=f"{bob}@example.com", password_hash="hash"),
            ])
            await session.flush()
            session.add(Document(
                id=doc_id, user_id=alice, original_name="test.pdf",
                storage_key=f"{alice}/{doc_id}.pdf", media_type="application/pdf",
                size_bytes=10, sha256="a" * 64, status="failed",
            ))
            await session.flush()
            session.add(Chunk(
                document_id=doc_id, user_id=alice, ordinal=0, page_number=1,
                original_text="test", normalized_text="test",
            ))

        async with maker() as session:
            with pytest.raises(lifecycle.DocumentNotFound):
                await lifecycle.retry_document(
                    session, user_id=bob, document_id=doc_id, settings=settings
                )
            await session.rollback()
            retried = await lifecycle.retry_document(
                session, user_id=alice, document_id=doc_id, settings=settings
            )
            assert retried.status == "queued"
            assert retried.failure_reason is None
            remaining = (await session.scalars(
                select(Chunk).where(Chunk.document_id == doc_id)
            )).all()
            assert remaining == []

        async with maker() as session:
            with pytest.raises(lifecycle.DocumentNotFound):
                await lifecycle.delete_document(
                    session, user_id=bob, document_id=doc_id, settings=settings
                )
            await session.rollback()
            await lifecycle.delete_document(
                session, user_id=alice, document_id=doc_id, settings=settings
            )
            assert await session.get(Document, doc_id) is None
        assert not pdf.exists()
        assert cleaned == [(alice, doc_id), (alice, doc_id)]
    finally:
        async with maker.begin() as session:
            await session.execute(delete(User).where(User.id.in_([alice, bob])))
        await engine.dispose()
