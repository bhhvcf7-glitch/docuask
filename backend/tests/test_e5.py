import pytest

from app.retrieval.embeddings import E5Embeddings


class FakeVectors:
    def __init__(self, count: int):
        self.count = count

    def tolist(self):
        return [[0.6, 0.8, 0.0] for _ in range(self.count)]


class FakeModel:
    def __init__(self) -> None:
        self.inputs: list[list[str]] = []

    def encode(self, texts, **kwargs):
        self.inputs.append(texts)
        assert kwargs["normalize_embeddings"] is True
        return FakeVectors(len(texts))


@pytest.mark.asyncio
async def test_e5_uses_query_and_passage_prefixes(monkeypatch) -> None:
    model = FakeModel()
    monkeypatch.setattr("app.retrieval.embeddings.load_model", lambda: model)
    encoder = E5Embeddings()
    assert await encoder.documents(["أَهْلًا ١٢٣", "English"]) == [
        [0.6, 0.8, 0.0], [0.6, 0.8, 0.0]
    ]
    assert await encoder.query("إِلَى ٤") == [0.6, 0.8, 0.0]
    assert model.inputs == [
        ["passage: اهلا 123", "passage: English"],
        ["query: الي 4"],
    ]
