import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.retrieval.vectors import VectorIndex
from app.services.document_lifecycle import remove_document_vectors

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_VECTOR_TESTS") != "1",
        reason="Requires Qdrant and RUN_VECTOR_TESTS=1",
    ),
]


async def test_deleting_vectors_never_removes_another_users_points() -> None:
    settings = Settings(_env_file=None, qdrant_collection=f"test_{uuid4().hex}")
    alice, bob, alice_doc, bob_doc = uuid4(), uuid4(), uuid4(), uuid4()
    first = SimpleNamespace(id=uuid4(), ordinal=0, page_number=2)
    second = SimpleNamespace(id=uuid4(), ordinal=0, page_number=3)
    client = AsyncQdrantClient(url=settings.qdrant_url)
    index = VectorIndex(client, settings.qdrant_collection, 3)
    try:
        await index.ensure_collection()
        await index.upsert(
            user_id=alice, document_id=alice_doc,
            chunks=[first], vectors=[[1.0, 0.0, 0.0]],
        )
        await index.upsert(
            user_id=bob, document_id=bob_doc,
            chunks=[second], vectors=[[1.0, 0.0, 0.0]],
        )
        await remove_document_vectors(settings, alice, alice_doc)

        assert await index.search(user_id=alice, vector=[1.0, 0.0, 0.0]) == []
        remaining = await index.search(user_id=bob, vector=[1.0, 0.0, 0.0])
        assert [hit.chunk_id for hit in remaining] == [second.id]
        assert (await client.count(
            collection_name=settings.qdrant_collection, exact=True
        )).count == 1
    finally:
        if await client.collection_exists(settings.qdrant_collection):
            await client.delete_collection(settings.qdrant_collection)
        await client.close()
