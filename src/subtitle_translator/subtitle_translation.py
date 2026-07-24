"""Batch translation orchestration for subtitle files."""

from __future__ import annotations

from subtitle_translator.batch import (
    BatchItem,
    BatchTranslation,
    TranslationContextItem,
)
from subtitle_translator.glossary import Glossary, validate_glossary_languages
from subtitle_translator.models import Subtitle, SubtitleFile
from subtitle_translator.providers.base import (
    BatchTranslationRequest,
    TranslationProvider,
)


class SubtitleTranslationError(ValueError):
    """Raised when a provider returns an invalid subtitle batch."""


class SubtitleTranslationService:
    """Translate subtitle files in sequential provider-neutral batches."""

    def __init__(
        self,
        provider: TranslationProvider,
        source_language: str,
        target_language: str,
        batch_size: int,
        glossary: Glossary | None = None,
        context_size: int = 10,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        if context_size < 0:
            raise ValueError("context_size must not be negative.")

        self._provider = provider
        self._source_language = source_language
        self._target_language = target_language
        self._batch_size = batch_size
        self._glossary = glossary
        self._context_size = context_size

        if glossary is not None:
            validate_glossary_languages(glossary, source_language, target_language)

    def translate(self, subtitle_file: SubtitleFile) -> SubtitleFile:
        """Translate every subtitle and return a new subtitle file."""

        translated_subtitles: list[Subtitle] = []
        rolling_context: list[TranslationContextItem] = []

        for start in range(0, len(subtitle_file.subtitles), self._batch_size):
            subtitles = subtitle_file.subtitles[start : start + self._batch_size]
            items = [BatchItem(id=subtitle.index, text=subtitle.text) for subtitle in subtitles]
            request = BatchTranslationRequest(
                items=tuple(items),
                source_language=self._source_language,
                target_language=self._target_language,
                glossary=self._glossary,
                context=(
                    tuple(rolling_context)
                    if self._context_size > 0
                    else None
                ),
            )
            translations = self._provider.translate_batch(request)
            translations_by_id = self._validate_translations(items, translations)

            accepted_subtitles = [
                Subtitle(
                    index=subtitle.index,
                    start=subtitle.start,
                    end=subtitle.end,
                    text=translations_by_id[subtitle.index].text,
                )
                for subtitle in subtitles
            ]
            translated_subtitles.extend(accepted_subtitles)

            if self._context_size > 0:
                rolling_context.extend(
                    TranslationContextItem(
                        id=source.index,
                        source_text=source.text,
                        translated_text=translated.text,
                    )
                    for source, translated in zip(
                        subtitles,
                        accepted_subtitles,
                        strict=True,
                    )
                )
                rolling_context = rolling_context[-self._context_size :]

        return SubtitleFile(subtitles=translated_subtitles)

    @staticmethod
    def _validate_translations(
        items: list[BatchItem],
        translations: list[BatchTranslation],
    ) -> dict[int, BatchTranslation]:
        expected_ids = [item.id for item in items]

        if len(translations) < len(items):
            raise SubtitleTranslationError(
                "Provider returned missing translations: "
                f"expected {len(items)} items, received {len(translations)}."
            )
        if len(translations) > len(items):
            raise SubtitleTranslationError(
                "Provider returned extra translations: "
                f"expected {len(items)} items, received {len(translations)}."
            )

        expected_id_set = set(expected_ids)
        translations_by_id: dict[int, BatchTranslation] = {}

        for translation in translations:
            if translation.id in translations_by_id:
                raise SubtitleTranslationError(
                    f"Provider returned duplicate translation ID: {translation.id}."
                )
            if translation.id not in expected_id_set:
                raise SubtitleTranslationError(
                    f"Provider returned unknown translation ID: {translation.id}."
                )

            translations_by_id[translation.id] = translation

        missing_ids = expected_id_set - translations_by_id.keys()
        if missing_ids:
            ids = ", ".join(str(item_id) for item_id in sorted(missing_ids))
            raise SubtitleTranslationError(f"Provider omitted translation IDs: {ids}.")

        return translations_by_id
