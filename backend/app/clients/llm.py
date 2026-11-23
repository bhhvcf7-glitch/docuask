import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings


class ProviderUnavailable(Exception):
    pass


class ProviderNotConfigured(Exception):
    pass


class OpenAICompatible:
    def __init__(self, url: str, model: str, key: str):
        self.url, self.model, self.key = url.rstrip("/"), model, key

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", f"{self.url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.key}"},
                    json={"model": self.model, "messages": messages, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        item = line[5:].strip()
                        if item == "[DONE]":
                            return
                        if item:
                            value = json.loads(item)["choices"][0]["delta"].get("content")
                            if value:
                                yield value
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise ProviderUnavailable from exc


class Ollama:
    def __init__(self, url: str, model: str):
        self.url, self.model = url.rstrip("/"), model

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", f"{self.url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        payload = json.loads(line)
                        if payload.get("error"):
                            raise ProviderUnavailable
                        value = payload.get("message", {}).get("content")
                        if value:
                            yield value
                        if payload.get("done"):
                            return
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise ProviderUnavailable from exc


def make_provider(settings: Settings) -> OpenAICompatible | Ollama:
    if settings.llm_provider == "ollama":
        return Ollama(settings.ollama_url, settings.llm_model)
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise ProviderNotConfigured
    return OpenAICompatible(
        settings.openai_base_url,
        settings.llm_model,
        settings.openai_api_key.get_secret_value(),
    )
