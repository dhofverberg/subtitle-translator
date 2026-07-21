from types import SimpleNamespace
from typing import Any

import pytest

from subtitle_translator.prompts import build_prompt
from subtitle_translator.providers import (
    OpenAIProvider,
    OpenAIProviderError,
    TranslationRequest,
)


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


def test_translate_uses_responses_api_with_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    client = FakeClient("Hej")
    provider = OpenAIProvider(client=client)
    request = TranslationRequest(
        text="Hello",
        source_language="English",
        target_language="Swedish",
    )

    result = provider.translate(request)

    assert result == "Hej"
    assert client.responses.calls == [
        {
            "model": "configured-model",
            "instructions": build_prompt("English", "Swedish"),
            "input": "Hello",
        }
    ]


def test_translate_rejects_empty_output():
    client = FakeClient("   ")
    provider = OpenAIProvider(client=client, model="explicit-model")
    request = TranslationRequest("Hello", "English", "Swedish")

    with pytest.raises(OpenAIProviderError, match="empty translation"):
        provider.translate(request)

    assert client.responses.calls[0]["model"] == "explicit-model"


def test_provider_creates_default_openai_client(monkeypatch):
    client = FakeClient("Hej")
    constructor_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def fake_openai(*args: Any, **kwargs: Any) -> FakeClient:
        constructor_calls.append((args, kwargs))
        return client

    monkeypatch.setattr(
        "subtitle_translator.providers.openai_provider.OpenAI",
        fake_openai,
    )

    provider = OpenAIProvider(model="explicit-model")
    result = provider.translate(TranslationRequest("Hello", "English", "Swedish"))

    assert result == "Hej"
    assert constructor_calls == [((), {})]
