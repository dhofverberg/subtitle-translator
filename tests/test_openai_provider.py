from types import SimpleNamespace
from typing import Any

import pytest
from openai import OpenAIError

from subtitle_translator.batch import (
    BatchItem,
    BatchProtocolError,
    BatchTranslation,
    serialize_batch,
)
from subtitle_translator.prompts import build_batch_prompt, build_prompt
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


class FailingResponses:
    def __init__(self, error: OpenAIError) -> None:
        self.error = error

    def create(self, **kwargs: Any) -> SimpleNamespace:
        raise self.error


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


def test_provider_wraps_openai_client_initialization_errors(monkeypatch):
    error = OpenAIError("secret initialization detail")

    def fail_openai() -> None:
        raise error

    monkeypatch.setattr(
        "subtitle_translator.providers.openai_provider.OpenAI",
        fail_openai,
    )

    with pytest.raises(
        OpenAIProviderError,
        match="OpenAI client initialization failed",
    ) as exc_info:
        OpenAIProvider(model="explicit-model")

    assert exc_info.value.__cause__ is error
    assert "secret initialization detail" not in str(exc_info.value)


def test_translate_wraps_openai_sdk_errors():
    error = OpenAIError("Authorization: Bearer secret")
    client = SimpleNamespace(responses=FailingResponses(error))
    provider = OpenAIProvider(client=client, model="explicit-model")

    with pytest.raises(OpenAIProviderError, match="OpenAI translation request failed") as exc_info:
        provider.translate(TranslationRequest("Hello", "English", "Swedish"))

    assert exc_info.value.__cause__ is error
    assert "secret" not in str(exc_info.value)


def test_translate_batch_wraps_openai_sdk_errors():
    error = OpenAIError("Authorization: Bearer secret")
    client = SimpleNamespace(responses=FailingResponses(error))
    provider = OpenAIProvider(client=client, model="explicit-model")

    with pytest.raises(
        OpenAIProviderError,
        match="OpenAI batch translation request failed",
    ) as exc_info:
        provider.translate_batch([BatchItem(1, "Hello")], "English", "Swedish")

    assert exc_info.value.__cause__ is error
    assert "secret" not in str(exc_info.value)


def test_translate_batch_uses_one_call_and_restores_input_order():
    client = FakeClient(
        '[{"id": 3, "text": "Adjö"}, '
        '{"id": 7, "text": "Hej\\nvärlden 👋"}]'
    )
    provider = OpenAIProvider(client=client, model="batch-model")
    items = [
        BatchItem(id=7, text="Hello\nworld 👋"),
        BatchItem(id=3, text="Goodbye"),
    ]

    translations = provider.translate_batch(items, "English", "Swedish")

    assert translations == [
        BatchTranslation(id=7, text="Hej\nvärlden 👋"),
        BatchTranslation(id=3, text="Adjö"),
    ]
    assert client.responses.calls == [
        {
            "model": "batch-model",
            "instructions": build_batch_prompt("English", "Swedish"),
            "input": serialize_batch(items),
        }
    ]
    assert len(client.responses.calls) == 1


def test_translate_batch_rejects_empty_input_without_api_call():
    client = FakeClient("[]")
    provider = OpenAIProvider(client=client, model="batch-model")

    with pytest.raises(ValueError, match="must not be empty"):
        provider.translate_batch([], "English", "Swedish")

    assert client.responses.calls == []


@pytest.mark.parametrize(
    "response_text",
    [
        "not JSON",
        '[{"id": 1, "text": "Ett"}]',
        (
            '[{"id": 1, "text": "Ett"}, '
            '{"id": 2, "text": "Två"}, '
            '{"id": 3, "text": "Tre"}]'
        ),
        '[{"id": 1, "text": "Ett"}, {"id": 1, "text": "Ett igen"}]',
        '[{"id": 1, "text": "Ett"}, {"id": 3, "text": "Tre"}]',
        '[{"id": 1, "text": "Ett"}, {"id": 2, "text": "   "}]',
    ],
    ids=[
        "invalid-json",
        "missing-id",
        "extra-id",
        "duplicate-id",
        "unknown-id",
        "blank-text",
    ],
)
def test_translate_batch_wraps_malformed_output(response_text):
    client = FakeClient(response_text)
    provider = OpenAIProvider(client=client, model="batch-model")
    items = [BatchItem(1, "One"), BatchItem(2, "Two")]

    with pytest.raises(OpenAIProviderError, match="invalid batch translation") as exc_info:
        provider.translate_batch(items, "English", "Swedish")

    assert isinstance(exc_info.value.__cause__, BatchProtocolError)
    assert len(client.responses.calls) == 1
