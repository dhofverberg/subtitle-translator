from __future__ import annotations

from datetime import timedelta

import pytest

from subtitle_translator.batch import BatchItem, BatchTranslation
from subtitle_translator.models import Subtitle, SubtitleFile
from subtitle_translator.providers.base import TranslationProvider, TranslationRequest
from subtitle_translator.subtitle_translation import (
    SubtitleTranslationError,
    SubtitleTranslationService,
)


class FakeProvider(TranslationProvider):
    def __init__(
        self,
        responses: list[list[BatchTranslation]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.responses = responses
        self.error = error
        self.calls: list[tuple[list[BatchItem], str, str]] = []

    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError

    def translate_batch(
        self,
        items: list[BatchItem],
        source_language: str,
        target_language: str,
    ) -> list[BatchTranslation]:
        self.calls.append((list(items), source_language, target_language))

        if self.error is not None:
            raise self.error
        if self.responses is not None:
            return self.responses[len(self.calls) - 1]

        return [
            BatchTranslation(id=item.id, text=f"Translated: {item.text}") for item in items
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
    assert provider.calls == [
        (
            [BatchItem(1, "One"), BatchItem(2, "Two")],
            "English",
            "Swedish",
        )
    ]


def test_translate_uses_sequential_batches_and_final_partial_batch():
    provider = FakeProvider()
    service = SubtitleTranslationService(provider, "English", "Swedish", batch_size=2)
    subtitle_file = SubtitleFile([make_subtitle(index) for index in range(1, 6)])

    result = service.translate(subtitle_file)

    assert len(provider.calls) == 3
    assert [[item.id for item in call[0]] for call in provider.calls] == [
        [1, 2],
        [3, 4],
        [5],
    ]
    assert [subtitle.index for subtitle in result.subtitles] == [1, 2, 3, 4, 5]


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
