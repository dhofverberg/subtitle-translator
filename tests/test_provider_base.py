from dataclasses import FrozenInstanceError

import pytest

from subtitle_translator.batch import BatchItem, BatchTranslation
from subtitle_translator.providers import TranslationProvider, TranslationRequest
from subtitle_translator.providers.base import (
    TranslationProvider as BaseTranslationProvider,
)
from subtitle_translator.providers.base import TranslationRequest as BaseTranslationRequest


def test_translation_request_contains_translation_input():
    request = TranslationRequest(
        text="Hello",
        source_language="English",
        target_language="Swedish",
    )

    assert request.text == "Hello"
    assert request.source_language == "English"
    assert request.target_language == "Swedish"


def test_translation_request_is_immutable():
    request = TranslationRequest("Hello", "English", "Swedish")

    with pytest.raises(FrozenInstanceError):
        request.text = "Goodbye"  # type: ignore[misc]


def test_translation_provider_is_abstract():
    with pytest.raises(TypeError):
        TranslationProvider()


def test_translation_provider_can_be_implemented():
    class EchoProvider(TranslationProvider):
        def translate(self, request: TranslationRequest) -> str:
            return request.text

        def translate_batch(
            self,
            items: list[BatchItem],
            source_language: str,
            target_language: str,
        ) -> list[BatchTranslation]:
            return [BatchTranslation(item.id, item.text) for item in items]

    request = TranslationRequest("Hello", "English", "Swedish")

    assert EchoProvider().translate(request) == "Hello"

    items = [BatchItem(1, "Hello")]
    assert EchoProvider().translate_batch(items, "English", "Swedish") == [
        BatchTranslation(1, "Hello")
    ]


def test_provider_classes_are_exported_from_package():
    assert TranslationProvider is BaseTranslationProvider
    assert TranslationRequest is BaseTranslationRequest
