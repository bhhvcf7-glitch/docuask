import os
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.repositories import get_document, list_document_chunks
from app.db.session import database_url

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1",
        reason="Set RUN_DB_TESTS=1 after applying migrations to PostgreSQL",
    ),
]


async def test_other_user_cannot_read_or_attach_chunks() -> None:
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as db:
                    alice, bob, doc_id = uuid4(), uuid4(), uuid4()
                    db.add_all([
                        User(id=alice, email=f"{alice}@example.com", password_hash="hash"),
                        User(id=bob, email=f"{bob}@example.com", password_hash="hash"),
                    ])
                    await db.flush()
                    db.add(Document(
                        id=doc_id, user_id=alice, original_name="file.pdf",
                        storage_key="a/file.pdf", media_type="application/pdf",
                        size_bytes=100, sha256="a" * 64, status="ready",
                    ))
                    await db.flush()
                    db.add(Chunk(
                        user_id=alice, document_id=doc_id, ordinal=0, page_number=2,
                        original_text="مرحبا", normalized_text="مرحبا",
                    ))
                    await db.flush()

                    assert await get_document(db, user_id=alice, document_id=doc_id)
                    assert await get_document(db, user_id=bob, document_id=doc_id) is None
                    assert len(await list_document_chunks(
                        db, user_id=alice, document_id=doc_id
                    )) == 1
                    assert await list_document_chunks(db, user_id=bob, document_id=doc_id) == []

                    with pytest.raises(IntegrityError):
                        async with db.begin_nested():
                            db.add(Chunk(
                                user_id=bob, document_id=doc_id, ordinal=1,
                                page_number=1, original_text="stolen",
                                normalized_text="stolen",
                            ))
                            await db.flush()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def test_same_user_cannot_upload_same_hash_twice() -> None:
    engine = create_async_engine(database_url(Settings(_env_file=None)))
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as db:
                    owner = uuid4()
                    db.add(User(id=owner, email=f"{owner}@example.com", password_hash="hash"))
                    await db.flush()
                    first = Document(
                        user_id=owner, original_name="first.pdf", storage_key="first",
                        media_type="application/pdf", size_bytes=10,
                        sha256="b" * 64, status="queued",
                    )
                    db.add(first)
                    await db.flush()
                    with pytest.raises(IntegrityError):
                        async with db.begin_nested():
                            db.add(Document(
                                user_id=owner, original_name="second.pdf",
                                storage_key="second", media_type="application/pdf",
                                size_bytes=10, sha256="b" * 64, status="queued",
                            ))
                            await db.flush()
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
