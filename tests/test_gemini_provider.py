from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from subtitle_translator.batch import BatchItem, BatchProtocolError, TranslationContextItem
from subtitle_translator.glossary import Glossary, GlossaryTerm
from subtitle_translator.providers.base import BatchTranslationRequest
from subtitle_translator.providers.gemini_provider import GeminiProvider, GeminiProviderError


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.models = FakeModels(responses)


def response(
    text: str | None,
    *,
    finish_reason: str = "STOP",
    prompt_feedback: object | None = None,
) -> SimpleNamespace:
    parts = [] if text is None else [SimpleNamespace(text=text)]
    return SimpleNamespace(
        prompt_feedback=prompt_feedback,
        candidates=[
            SimpleNamespace(
                finish_reason=finish_reason,
                content=SimpleNamespace(parts=parts),
            )
        ],
    )


def request(
    *,
    glossary: Glossary | None = None,
    context: tuple[TranslationContextItem, ...] | None = None,
) -> BatchTranslationRequest:
    return BatchTranslationRequest(
        items=(
            BatchItem(30, "Hello\nworld 👋"),
            BatchItem(10, "The café is open."),
        ),
        source_language="English",
        target_language="Swedish",
        glossary=glossary,
        context=context,
    )


def test_translate_batch_uses_injected_client_structured_output_and_separate_data():
    client = FakeClient(
        [response('[{"id": 10, "text": "Kaféet är öppet."}, {"id": 30, "text": "Hej\\nvärlden 👋"}]')]
    )
    glossary = Glossary("English", "Swedish", (GlossaryTerm("café", "kafé"),))
    context = (TranslationContextItem(5, "Earlier", "Tidigare"),)
    provider = GeminiProvider(client=client, model="gemini-test")

    translations = provider.translate_batch(request(glossary=glossary, context=context))

    assert [(item.id, item.text) for item in translations] == [
        (30, "Hej\nvärlden 👋"),
        (10, "Kaféet är öppet."),
    ]
    call = client.models.calls[0]
    assert call["model"] == "gemini-test"
    assert json.loads(call["contents"]) == {
        "glossary": {
            "source_language": "English",
            "target_language": "Swedish",
            "terms": [{"source": "café", "target": "kafé"}],
        },
        "context": [{"id": 5, "source": "Earlier", "translation": "Tidigare"}],
        "items": [
            {"id": 30, "text": "Hello\nworld 👋"},
            {"id": 10, "text": "The café is open."},
        ],
    }
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_json_schema["items"]["required"] == ["id", "text"]


@pytest.mark.parametrize(
    "response_text",
    [
        "not JSON",
        '[{"id": 30, "text": "Hej"}, {"id": 30, "text": "Hej igen"}]',
        '[{"id": 30, "text": "Hej"}, {"id": 99, "text": "Okänd"}]',
        '[{"id": 30, "text": "Hej"}]',
        '[{"id": 30, "text": "Hej"}, {"id": 10, "text": "  "}]',
    ],
)
def test_translate_batch_wraps_invalid_responses(response_text: str):
    client = FakeClient([response(response_text)])
    provider = GeminiProvider(client=client, model="gemini-test")

    with pytest.raises(GeminiProviderError, match="invalid batch translation") as exc_info:
        provider.translate_batch(request())

    assert isinstance(exc_info.value.__cause__, BatchProtocolError)


@pytest.mark.parametrize(
    "sdk_response, message",
    [
        (response(None), "empty translation response"),
        (response("[]", prompt_feedback=object()), "blocked"),
        (response("[]", finish_reason="SAFETY"), "blocked"),
        (response("[]", finish_reason="MAX_TOKENS"), "incomplete"),
    ],
)
def test_translate_batch_rejects_empty_blocked_and_incomplete_responses(
    sdk_response: object,
    message: str,
):
    provider = GeminiProvider(client=FakeClient([sdk_response]), model="gemini-test")

    with pytest.raises(GeminiProviderError, match=message):
        provider.translate_batch(request())


def test_translate_batch_sanitizes_sdk_errors():
    secret = "gemini-secret-value"
    provider = GeminiProvider(
        client=FakeClient([errors.APIError(500, {"Authorization": secret}, None)]),
        model="gemini-test",
    )

    with pytest.raises(GeminiProviderError, match="request failed") as exc_info:
        provider.translate_batch(request())

    assert secret not in str(exc_info.value)
