from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.search import search_documents


class FakeEmbeddings:
    async def query(self, question):
        return [1.0, 0.0, 0.0]


class FakeIndex:
    def __init__(self):
        self.calls = []

    async def search(self, *, user_id, vector, limit):
        self.calls.append((user_id, vector, limit))
        return []


@pytest.mark.asyncio
async def test_search_reuses_injected_index_with_owner_filter() -> None:
    index = FakeIndex()
    owner = uuid4()
    hits = await search_documents(
        None,
        user_id=owner,
        question="What happened?",
        limit=3,
        settings=Settings(_env_file=None),
        embeddings=FakeEmbeddings(),
        index=index,
    )
    assert hits == []
    assert index.calls == [(owner, [1.0, 0.0, 0.0], 3)]
