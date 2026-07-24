from __future__ import annotations

from datetime import timedelta

import pytest

from subtitle_translator.batch import (
    BatchItem,
    BatchTranslation,
    TranslationContextItem,
)
from subtitle_translator.glossary import Glossary, GlossaryError, GlossaryTerm
from subtitle_translator.models import Subtitle, SubtitleFile
from subtitle_translator.providers.base import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationRequest,
)
from subtitle_translator.subtitle_translation import (
    SubtitleTranslationError,
    SubtitleTranslationService,
)


class FakeProvider(TranslationProvider):
    def __init__(
        self,
        responses: list[list[BatchTranslation]] | None = None,
        error: Exception | None = None,
        error_on_call: int | None = None,
    ) -> None:
        self.responses = responses
        self.error = error
        self.error_on_call = error_on_call
        self.calls: list[BatchTranslationRequest] = []

    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError

    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        self.calls.append(request)

        if self.error is not None and (
            self.error_on_call is None
            or len(self.calls) == self.error_on_call
        ):
            raise self.error
        if self.responses is not None:
            return self.responses[len(self.calls) - 1]

        return [
            BatchTranslation(id=item.id, text=f"Translated: {item.text}")
            for item in request.items
        ]


def make_subtitle(index: int, text: str | None = None) -> Subtitle:
    return Subtitle(
        index=index,
        start=timedelta(seconds=index * 2),
        end=timedelta(seconds=index * 2 + 1),
        text=text if text is not None else f"Subtitle {index}",
    )


def test_translate_one_batch_constructs_items_and_returns_translations():
    provider = FakeProvider(
        responses=[
            [
                BatchTranslation(1, "Ett"),
                BatchTranslation(2, "Två"),
            ]
        ]
    )
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=10)
    subtitle_file = SubtitleFile([make_subtitle(1, "One"), make_subtitle(2, "Two")])

    result = service.translate(subtitle_file)

    assert [subtitle.text for subtitle in result.subtitles] == ["Ett", "Två"]
    assert provider.calls[0].items == (
        BatchItem(1, "One"),
        BatchItem(2, "Two"),
    )
    assert provider.calls[0].source_language == "English"
    assert provider.calls[0].target_language == "Swedish"
    assert provider.calls[0].context == ()


def test_translate_uses_sequential_batches_and_final_partial_batch():
    provider = FakeProvider()
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=2)
    subtitle_file = SubtitleFile([make_subtitle(index) for index in range(1, 6)])

    result = service.translate(subtitle_file)

    assert len(provider.calls) == 3
    assert [[item.id for item in call.items] for call in provider.calls] == [
        [1, 2],
        [3, 4],
        [5],
    ]
    assert [subtitle.index for subtitle in result.subtitles] == [1, 2, 3, 4, 5]


def test_translate_passes_glossary_to_every_batch():
    glossary = Glossary(
        source_language="English",
        target_language="Swedish",
        terms=(GlossaryTerm("warp drive", "warpdrift"),),
    )
    provider = FakeProvider()
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        glossary=glossary,
    )

    service.translate(SubtitleFile([make_subtitle(1), make_subtitle(2)]))

    assert [call.glossary for call in provider.calls] == [glossary, glossary]
    assert provider.calls[0].context == ()
    assert provider.calls[1].context == (
        TranslationContextItem(1, "Subtitle 1", "Translated: Subtitle 1"),
    )


def test_rejects_glossary_language_mismatch_before_provider_call():
    glossary = Glossary(
        source_language="German",
        target_language="Swedish",
        terms=(),
    )
    provider = FakeProvider()

    with pytest.raises(GlossaryError, match="source language"):
        SubtitleTranslationService(
            provider,
            "English",
            "Swedish",
            batch_size=1,
            glossary=glossary,
        )

    assert provider.calls == []


def test_translate_preserves_structure_without_mutating_input():
    original_subtitles = [
        make_subtitle(4, "Hello\nworld 👋"),
        make_subtitle(9, "Goodbye"),
    ]
    original_values = [
        Subtitle(item.index, item.start, item.end, item.text) for item in original_subtitles
    ]
    subtitle_file = SubtitleFile(original_subtitles)
    provider = FakeProvider()
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=2)

    result = service.translate(subtitle_file)

    assert result is not subtitle_file
    assert result.subtitles is not subtitle_file.subtitles
    assert subtitle_file.subtitles == original_values
    assert all(
        translated is not original
        for translated, original in zip(result.subtitles, original_subtitles)
    )
    assert [item.index for item in result.subtitles] == [4, 9]
    assert [item.start for item in result.subtitles] == [item.start for item in original_values]
    assert [item.end for item in result.subtitles] == [item.end for item in original_values]
    assert [item.text for item in result.subtitles] == [
        "Translated: Hello\nworld 👋",
        "Translated: Goodbye",
    ]


def test_translate_empty_file_does_not_call_provider():
    provider = FakeProvider()
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=2)

    result = service.translate(SubtitleFile())

    assert result == SubtitleFile()
    assert provider.calls == []


@pytest.mark.parametrize("batch_size", [0, -1])
def test_rejects_invalid_batch_size(batch_size):
    with pytest.raises(ValueError, match="batch_size must be greater than zero"):
        SubtitleTranslationService(FakeProvider(), "English", "Swedish", batch_size)


def test_rejects_negative_context_size():
    with pytest.raises(ValueError, match="context_size must not be negative"):
        SubtitleTranslationService(
            FakeProvider(),
            "English",
            "Swedish",
            batch_size=1,
            context_size=-1,
        )


def test_rolling_context_is_oldest_to_newest_and_limited():
    provider = FakeProvider()
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        context_size=2,
    )

    service.translate(SubtitleFile([make_subtitle(index) for index in range(1, 5)]))

    assert [call.context for call in provider.calls] == [
        (),
        (TranslationContextItem(1, "Subtitle 1", "Translated: Subtitle 1"),),
        (
            TranslationContextItem(1, "Subtitle 1", "Translated: Subtitle 1"),
            TranslationContextItem(2, "Subtitle 2", "Translated: Subtitle 2"),
        ),
        (
            TranslationContextItem(2, "Subtitle 2", "Translated: Subtitle 2"),
            TranslationContextItem(3, "Subtitle 3", "Translated: Subtitle 3"),
        ),
    ]


def test_context_size_zero_disables_context():
    provider = FakeProvider()
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        context_size=0,
    )

    service.translate(SubtitleFile([make_subtitle(1), make_subtitle(2)]))

    assert [call.context for call in provider.calls] == [None, None]


def test_context_pairs_source_with_accepted_translation_for_ambiguity():
    provider = FakeProvider(
        responses=[
            [BatchTranslation(10, "Hon är min mormor.")],
            [BatchTranslation(20, "Mormor kommer senare.")],
        ]
    )
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        context_size=10,
    )

    service.translate(
        SubtitleFile(
            [
                make_subtitle(
                    10,
                    "She is my mother's mother, my grandmother.",
                ),
                make_subtitle(20, "Grandmother will come later."),
            ]
        )
    )

    assert provider.calls[1].context == (
        TranslationContextItem(
            id=10,
            source_text="She is my mother's mother, my grandmother.",
            translated_text="Hon är min mormor.",
        ),
    )


def test_context_does_not_leak_between_service_calls():
    provider = FakeProvider()
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        context_size=10,
    )

    service.translate(SubtitleFile([make_subtitle(1)]))
    service.translate(SubtitleFile([make_subtitle(2)]))

    assert provider.calls[0].context == ()
    assert provider.calls[1].context == ()


def test_failed_batch_does_not_update_or_leak_context():
    error = RuntimeError("Provider failed")
    provider = FakeProvider(error=error, error_on_call=2)
    service = SubtitleTranslationService(
        provider,
        "English",
        "Swedish",
        batch_size=1,
        context_size=10,
    )

    with pytest.raises(RuntimeError):
        service.translate(SubtitleFile([make_subtitle(1), make_subtitle(2)]))

    provider.error = None
    service.translate(SubtitleFile([make_subtitle(3)]))

    assert provider.calls[1].context == (
        TranslationContextItem(1, "Subtitle 1", "Translated: Subtitle 1"),
    )
    assert provider.calls[2].context == ()


def test_provider_exceptions_propagate():
    error = RuntimeError("Provider failed")
    service = SubtitleTranslationService(
        FakeProvider(error=error),
        "English",
        "Swedish",
        batch_size=2,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service.translate(SubtitleFile([make_subtitle(1)]))

    assert exc_info.value is error


@pytest.mark.parametrize(
    ("translations", "message"),
    [
        ([BatchTranslation(1, "Ett")], "missing translations"),
        (
            [
                BatchTranslation(1, "Ett"),
                BatchTranslation(2, "Två"),
                BatchTranslation(3, "Tre"),
            ],
            "extra translations",
        ),
        (
            [BatchTranslation(1, "Ett"), BatchTranslation(1, "Ett igen")],
            "duplicate translation ID: 1",
        ),
        (
            [BatchTranslation(1, "Ett"), BatchTranslation(3, "Tre")],
            "unknown translation ID: 3",
        ),
    ],
    ids=["missing", "extra", "duplicate", "unknown"],
)
def test_rejects_malformed_provider_results(translations, message):
    provider = FakeProvider(responses=[translations])
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=2)
    subtitle_file = SubtitleFile([make_subtitle(1), make_subtitle(2)])

    with pytest.raises(SubtitleTranslationError, match=message):
        service.translate(subtitle_file)
