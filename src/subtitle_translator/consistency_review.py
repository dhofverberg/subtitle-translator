"""Chunked provider-neutral consistency review orchestration."""

from __future__ import annotations

from .batch import TranslationContextItem
from .consistency import (
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewRequest,
    normalize_consistency_report,
)
from .glossary import Glossary, validate_glossary_languages
from .models import SubtitleFile


class ConsistencyReviewError(ValueError):
    """Raised when source and translated subtitle files cannot be reviewed."""


class ConsistencyReviewService:
    """Review accepted subtitle pairs in deterministic overlapping chunks."""

    def __init__(
        self,
        reviewer: ConsistencyReviewer,
        source_language: str,
        target_language: str,
        glossary: Glossary | None = None,
        chunk_size: int = 100,
        overlap: int = 10,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")
        if overlap < 0:
            raise ValueError("overlap must not be negative.")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size.")
        if glossary is not None:
            validate_glossary_languages(glossary, source_language, target_language)

        self._reviewer = reviewer
        self._source_language = source_language
        self._target_language = target_language
        self._glossary = glossary
        self._chunk_size = chunk_size
        self._overlap = overlap

    def review(
        self,
        source_file: SubtitleFile,
        translated_file: SubtitleFile,
    ) -> ConsistencyReport:
        """Review a completed translation without modifying either file."""

        pairs = self._pair_subtitles(source_file, translated_file)
        findings = []

        for chunk in self._chunks(pairs):
            report = self._reviewer.review(
                ConsistencyReviewRequest(
                    items=chunk,
                    source_language=self._source_language,
                    target_language=self._target_language,
                    glossary=self._glossary,
                )
            )
            findings.extend(report.findings)

        return normalize_consistency_report(ConsistencyReport(tuple(findings)))

    def _chunks(
        self,
        items: tuple[TranslationContextItem, ...],
    ) -> tuple[tuple[TranslationContextItem, ...], ...]:
        chunks: list[tuple[TranslationContextItem, ...]] = []
        start = 0
        while start < len(items):
            end = min(start + self._chunk_size, len(items))
            chunks.append(items[start:end])
            if end == len(items):
                break
            start += self._chunk_size - self._overlap
        return tuple(chunks)

    @staticmethod
    def _pair_subtitles(
        source_file: SubtitleFile,
        translated_file: SubtitleFile,
    ) -> tuple[TranslationContextItem, ...]:
        if len(source_file.subtitles) != len(translated_file.subtitles):
            raise ConsistencyReviewError(
                "Source and translated files must contain the same number of subtitles."
            )

        pairs = []
        for position, (source, translated) in enumerate(
            zip(source_file.subtitles, translated_file.subtitles, strict=True)
        ):
            if source.index != translated.index:
                raise ConsistencyReviewError(
                    "Source and translated subtitle IDs differ at "
                    f"position {position}: {source.index} != {translated.index}."
                )
            pairs.append(
                TranslationContextItem(
                    id=source.index,
                    source_text=source.text,
                    translated_text=translated.text,
                )
            )
        return tuple(pairs)
