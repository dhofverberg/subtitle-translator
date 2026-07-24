from dataclasses import FrozenInstanceError

import pytest

from subtitle_translator.batch import (
    BatchItem,
    BatchTranslation,
    TranslationContextItem,
)
from subtitle_translator.providers import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationRequest,
)
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
            request: BatchTranslationRequest,
        ) -> list[BatchTranslation]:
            return [
                BatchTranslation(item.id, item.text)
                for item in request.items
            ]

    request = TranslationRequest("Hello", "English", "Swedish")

    assert EchoProvider().translate(request) == "Hello"

    items = [BatchItem(1, "Hello")]
    batch_request = BatchTranslationRequest(
        tuple(items),
        "English",
        "Swedish",
    )
    assert EchoProvider().translate_batch(batch_request) == [
        BatchTranslation(1, "Hello")
    ]


def test_batch_translation_request_is_immutable_and_keeps_context_separate():
    context = TranslationContextItem(1, "Grandmother called.", "Mormor ringde.")
    request = BatchTranslationRequest(
        items=(BatchItem(2, "Grandmother is here."),),
        source_language="English",
        target_language="Swedish",
        context=(context,),
    )

    assert request.context == (context,)

    with pytest.raises(FrozenInstanceError):
        request.context = None  # type: ignore[misc]


def test_translation_context_item_is_immutable():
    context = TranslationContextItem(1, "Source", "Translation")

    with pytest.raises(FrozenInstanceError):
        context.translated_text = "Changed"  # type: ignore[misc]


def test_batch_translation_request_rejects_context_id_collision():
    with pytest.raises(ValueError, match="must not overlap"):
        BatchTranslationRequest(
            items=(BatchItem(1, "Current"),),
            source_language="English",
            target_language="Swedish",
            context=(TranslationContextItem(1, "Previous", "Tidigare"),),
        )


def test_provider_classes_are_exported_from_package():
    from subtitle_translator.providers.base import (
        BatchTranslationRequest as BaseBatchTranslationRequest,
    )

    assert BatchTranslationRequest is BaseBatchTranslationRequest
    assert TranslationProvider is BaseTranslationProvider
    assert TranslationRequest is BaseTranslationRequest
