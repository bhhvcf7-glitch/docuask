import httpx
import pytest
from pydantic import SecretStr

from app.clients.llm import (
    Ollama,
    OpenAICompatible,
    ProviderNotConfigured,
    ProviderUnavailable,
    make_provider,
)
from app.core.config import Settings


@pytest.mark.asyncio
async def test_openai_compatible_stream_reads_delta_tokens(monkeypatch) -> None:
    def handle(request: httpx.Request):
        assert request.headers["Authorization"] == "Bearer testing"
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"مرحبا"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"!"}}]}\n\n'
            'data: [DONE]\n\n',
        )

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        "app.clients.llm.httpx.AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    stream = OpenAICompatible("http://local.test/v1", "model", "testing").stream([])
    assert [token async for token in stream] == ["مرحبا", "!"]


@pytest.mark.asyncio
async def test_ollama_stream_reads_ndjson(monkeypatch) -> None:
    def handle(request: httpx.Request):
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200, text='{"message":{"content":"Hello"},"done":false}\n'
            '{"message":{"content":"!"},"done":false}\n'
            '{"done":true}\n',
        )

    original = httpx.AsyncClient
    transport = httpx.MockTransport(handle)
    monkeypatch.setattr(
        "app.clients.llm.httpx.AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    assert [t async for t in Ollama("http://local.test", "model").stream([])] == [
        "Hello", "!"
    ]


@pytest.mark.asyncio
async def test_provider_http_failure_has_specific_exception(monkeypatch) -> None:
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    monkeypatch.setattr(
        "app.clients.llm.httpx.AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    with pytest.raises(ProviderUnavailable):
        _ = [t async for t in Ollama("http://local.test", "model").stream([])]


def test_provider_selection_requires_openai_key() -> None:
    assert isinstance(make_provider(Settings(_env_file=None, llm_provider="ollama")), Ollama)
    with pytest.raises(ProviderNotConfigured):
        make_provider(Settings(_env_file=None, llm_provider="openai", openai_api_key=None))
    provider = make_provider(Settings(
        _env_file=None, llm_provider="openai", openai_api_key=SecretStr("example"),
    ))
    assert isinstance(provider, OpenAICompatible)
