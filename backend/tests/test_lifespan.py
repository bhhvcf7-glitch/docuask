import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app import main as entrypoint
from app.core.config import Settings


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class FakeClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakeEmbeddings:
    dimension = 3


class FakeIndex:
    def __init__(self, client, collection, dimension):
        self.client = client
        self.collection = collection
        self.dimension = dimension
        self.checked = 0

    async def ensure_collection(self):
        self.checked += 1


@pytest.mark.asyncio
async def test_lifespan_initializes_once_and_closes_shared_resources(monkeypatch):
    settings = Settings(
        _env_file=None,
        postgres_password=SecretStr("test-only"),
        preload_embeddings=True,
    )
    engine, client = FakeEngine(), FakeClient()
    calls = []

    monkeypatch.setattr(entrypoint, "get_settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(entrypoint, "AsyncQdrantClient", lambda **kwargs: client)
    monkeypatch.setattr(entrypoint, "E5Embeddings", FakeEmbeddings)
    monkeypatch.setattr(entrypoint, "VectorIndex", FakeIndex)

    def preload():
        calls.append("preload")

    async def in_thread(func):
        func()

    async def recovery(settings, engine):
        calls.append("recovery")
        assert engine is shared_engine

    shared_engine = engine
    monkeypatch.setattr(entrypoint, "load_model", preload)
    monkeypatch.setattr(entrypoint, "run_in_threadpool", in_thread)
    monkeypatch.setattr(entrypoint, "fail_stale_ingestions", recovery)

    app = FastAPI()
    async with entrypoint.lifespan(app):
        resources = app.state.resources
        assert resources.engine is engine
        assert resources.qdrant is client
        assert resources.index.client is client
        assert resources.index.checked == 1
        assert resources.embeddings.dimension == 3
        assert calls == ["preload", "recovery"]
        assert not engine.disposed and not client.closed

    assert app.state.resources is None
    assert engine.disposed and client.closed


@pytest.mark.asyncio
async def test_test_mode_can_defer_embedding_model_load(monkeypatch):
    settings = Settings(
        _env_file=None,
        postgres_password=SecretStr("test-only"),
        preload_embeddings=False,
    )
    engine, client = FakeEngine(), FakeClient()
    called = []
    monkeypatch.setattr(entrypoint, "get_settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(entrypoint, "AsyncQdrantClient", lambda **kwargs: client)
    monkeypatch.setattr(entrypoint, "E5Embeddings", FakeEmbeddings)
    monkeypatch.setattr(entrypoint, "VectorIndex", FakeIndex)
    monkeypatch.setattr(entrypoint, "load_model", lambda: called.append("loaded"))

    async def recovery(settings, engine):
        return 0

    monkeypatch.setattr(entrypoint, "fail_stale_ingestions", recovery)
    app = FastAPI()
    async with entrypoint.lifespan(app):
        assert app.state.resources.index.checked == 1
        assert called == []
    assert engine.disposed and client.closed
