import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from app.retrieval.vectors import VectorIndex, point_id

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_VECTOR_TESTS") != "1",
        reason="Requires real Qdrant and RUN_VECTOR_TESTS=1",
    ),
]


async def test_qdrant_enforces_user_filter_and_idempotent_upsert() -> None:
    user_a, user_b, doc_a, doc_b = uuid4(), uuid4(), uuid4(), uuid4()
    collection = f"test_{uuid4().hex}"
    client = AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    try:
        index = VectorIndex(client, collection, 3)
        await index.ensure_collection()
        first = SimpleNamespace(id=uuid4(), ordinal=0, page_number=2)
        second = SimpleNamespace(id=uuid4(), ordinal=0, page_number=7)
        await index.upsert(
            user_id=user_a, document_id=doc_a,
            chunks=[first], vectors=[[1.0, 0.0, 0.0]],
        )
        await index.upsert(
            user_id=user_b, document_id=doc_b,
            chunks=[second], vectors=[[1.0, 0.0, 0.0]],
        )
        await index.upsert(
            user_id=user_a, document_id=doc_a,
            chunks=[first], vectors=[[1.0, 0.0, 0.0]],
        )
        assert point_id(doc_a, 0) == point_id(doc_a, 0)
        assert (await client.count(collection_name=collection, exact=True)).count == 2

        alice = await index.search(user_id=user_a, vector=[1, 0, 0])
        bob = await index.search(user_id=user_b, vector=[1, 0, 0])
        assert [hit.chunk_id for hit in alice] == [first.id]
        assert [hit.chunk_id for hit in bob] == [second.id]
        assert await index.search(user_id=uuid4(), vector=[1, 0, 0]) == []
    finally:
        if await client.collection_exists(collection):
            await client.delete_collection(collection)
        await client.close()


async def test_collection_rejects_different_vector_dimensions() -> None:
    collection = f"test_{uuid4().hex}"
    client = AsyncQdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
    try:
        index = VectorIndex(client, collection, 3)
        await index.ensure_collection()
        with pytest.raises(ValueError, match="dimension"):
            await VectorIndex(client, collection, 384).ensure_collection()
    finally:
        if await client.collection_exists(collection):
            await client.delete_collection(collection)
        await client.close()
