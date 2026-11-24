import os
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Chunk, Document, User
from app.db.session import database_url
from app.retrieval.vectors import VectorIndex
from app.services.search import search_documents

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1" or os.getenv("RUN_VECTOR_TESTS") != "1",
        reason="Requires migrated PostgreSQL and Qdrant",
    ),
]


class FakeEmbeddings:
    dimension = 3

    async def query(self, question: str) -> list[float]:
        return [1.0, 0.0, 0.0]


@pytest.mark.parametrize("mode", ["dense", "hybrid"])
async def test_search_resolves_only_ready_chunks_owned_by_requester(mode) -> None:
    settings = Settings(_env_file=None, retrieval_mode=mode)
    engine = create_async_engine(database_url(settings))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    index = VectorIndex(qdrant, f"test_{uuid4().hex}", 3)
    alice, bob = uuid4(), uuid4()
    try:
        await index.ensure_collection()
        async with sessions.begin() as session:
            session.add_all([
                User(id=alice, email=f"{alice}@example.com", password_hash="hash"),
                User(id=bob, email=f"{bob}@example.com", password_hash="hash"),
            ])
            await session.flush()
            records = []
            for owner, status in [(alice, "ready"), (bob, "ready"), (alice, "failed")]:
                doc_id = uuid4()
                document = Document(
                    id=doc_id, user_id=owner, original_name="notes.pdf",
                    storage_key=f"{doc_id}.pdf", media_type="application/pdf",
                    size_bytes=100, sha256=uuid4().hex.ljust(64, "a"), status=status,
                )
                session.add(document)
                await session.flush()
                chunk = Chunk(
                    user_id=owner, document_id=doc_id, ordinal=0,
                    page_number=3, original_text=f"Owner {owner}",
                    normalized_text="owner",
                )
                session.add(chunk)
                await session.flush()
                records.append((owner, document, chunk))
        for owner, document, chunk in records:
            await index.upsert(
                user_id=owner, document_id=document.id,
                chunks=[chunk], vectors=[[1, 0, 0]],
            )

        async with sessions() as session:
            alice_hits = await search_documents(
                session, user_id=alice, question="owner", limit=5,
                settings=settings, embeddings=FakeEmbeddings(), index=index,
            )
            bob_hits = await search_documents(
                session, user_id=bob, question="owner", limit=5,
                settings=settings, embeddings=FakeEmbeddings(), index=index,
            )
            assert [hit["chunk_id"] for hit in alice_hits] == [records[0][2].id]
            assert [hit["chunk_id"] for hit in bob_hits] == [records[1][2].id]
            assert alice_hits[0]["page_number"] == 3
            assert alice_hits[0]["filename"] == "notes.pdf"
    finally:
        async with sessions.begin() as session:
            await session.execute(delete(User).where(User.id.in_([alice, bob])))
        await engine.dispose()
        if await qdrant.collection_exists(index.collection):
            await qdrant.delete_collection(index.collection)
        await qdrant.close()
