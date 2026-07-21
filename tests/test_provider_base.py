from dataclasses import FrozenInstanceError

import pytest

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

    request = TranslationRequest("Hello", "English", "Swedish")

    assert EchoProvider().translate(request) == "Hello"


def test_provider_classes_are_exported_from_package():
    assert TranslationProvider is BaseTranslationProvider
    assert TranslationRequest is BaseTranslationRequest
