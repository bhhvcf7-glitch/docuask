from uuid import uuid4

import pytest

from app.core.config import Settings
from app.retrieval.reranker import reorder
from app.services import search


def test_reorder_preserves_cosine_and_stable_ties():
    hits = [{"score": 0.9}, {"score": 0.2}, {"score": 0.3}]
    assert reorder(hits, [0.1, 0.8, 0.8]) == [hits[1], hits[2], hits[0]]
    with pytest.raises(ValueError):
        reorder(hits, [float("nan"), 1, 2])
    with pytest.raises(ValueError):
        reorder(hits, [])


@pytest.mark.asyncio
async def test_rerank_operates_on_resolved_hits(monkeypatch):
    owner = uuid4()
    hits = [{"text": "one", "score": 0.8}, {"text": "اثنان", "score": 0.7}]

    class Embeddings:
        async def query(self, question):
            return [1.0]

    class Index:
        async def search(self, **kwargs):
            assert kwargs["user_id"] == owner
            assert kwargs["limit"] == 20
            return []

    async def resolve(session, user_id, matches):
        assert user_id == owner
        return hits

    async def rerank(question, resolved):
        assert question == "سؤال"
        assert resolved == hits
        return resolved[::-1]

    monkeypatch.setattr(search, "_resolve", resolve)
    monkeypatch.setattr(search, "rerank", rerank)
    result = await search.search_documents(
        None, user_id=owner, question="سؤال", limit=1,
        settings=Settings(_env_file=None, rerank_enabled=True),
        embeddings=Embeddings(), index=Index(),
    )
    assert result == [hits[1]]
