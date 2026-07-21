import pytest

from subtitle_translator.providers.base import TranslationProvider, TranslationRequest
from subtitle_translator.translator import Translator


class FakeProvider(TranslationProvider):
    def __init__(self, result: str = "Translated text", error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.requests: list[TranslationRequest] = []

    def translate(self, request: TranslationRequest) -> str:
        self.requests.append(request)

        if self.error is not None:
            raise self.error

        return self.result


def test_translate_text_constructs_request_with_languages():
    provider = FakeProvider()
    translator = Translator(
        provider=provider,
        source_language="English",
        target_language="Swedish",
    )

    translator.translate_text("Hello")

    assert provider.requests == [
        TranslationRequest(
            text="Hello",
            source_language="English",
            target_language="Swedish",
        )
    ]


def test_translate_text_returns_provider_translation():
    provider = FakeProvider(result="Hej")
    translator = Translator(provider, "English", "Swedish")

    assert translator.translate_text("Hello") == "Hej"


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_translate_text_rejects_blank_input(text):
    provider = FakeProvider()
    translator = Translator(provider, "English", "Swedish")

    with pytest.raises(ValueError, match="must not be blank"):
        translator.translate_text(text)

    assert provider.requests == []


def test_translate_text_propagates_provider_exceptions():
    error = RuntimeError("Provider failed")
    provider = FakeProvider(error=error)
    translator = Translator(provider, "English", "Swedish")

    with pytest.raises(RuntimeError) as exc_info:
        translator.translate_text("Hello")

    assert exc_info.value is error
