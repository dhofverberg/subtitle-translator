from pathlib import Path

from .consistency import (
    ConsistencyProtocolError,
    ConsistencyReviewer,
    ConsistencyReviewerError,
)
from .consistency_report import render_consistency_report, save_consistency_report
from .consistency_review import ConsistencyReviewError, ConsistencyReviewService
from .glossary import Glossary
from .providers.base import TranslationProvider
from .srt import load_srt, save_srt
from .subtitle_translation import SubtitleTranslationService


class TranslationInputError(ValueError):
    """Raised when application translation inputs are invalid."""


class ConsistencyReportGenerationError(RuntimeError):
    """Raised when review fails after the translated SRT was saved."""


def translate_srt_file(
    input_path: Path,
    output_path: Path,
    provider: TranslationProvider,
    source_language: str,
    target_language: str,
    batch_size: int,
    glossary: Glossary | None = None,
    context_size: int = 10,
    consistency_reviewer: ConsistencyReviewer | None = None,
    consistency_report_path: Path | None = None,
    review_chunk_size: int = 100,
    review_overlap: int = 10,
) -> None:
    """Load, translate, and save an SRT subtitle file."""

    if input_path.resolve() == output_path.resolve():
        raise TranslationInputError("Input and output paths must be different.")
    if (consistency_reviewer is None) != (consistency_report_path is None):
        raise TranslationInputError(
            "Consistency reviewer and report path must be supplied together."
        )
    if consistency_report_path is not None:
        report_path = consistency_report_path.resolve()
        if report_path == input_path.resolve():
            raise TranslationInputError(
                "Consistency report path must differ from the input path."
            )
        if report_path == output_path.resolve():
            raise TranslationInputError(
                "Consistency report path must differ from the translated output path."
            )
        if consistency_report_path.exists():
            raise FileExistsError(
                f"Consistency report already exists: {consistency_report_path}"
            )

    subtitle_file = load_srt(input_path)
    service = SubtitleTranslationService(
        provider=provider,
        source_language=source_language,
        target_language=target_language,
        batch_size=batch_size,
        glossary=glossary,
        context_size=context_size,
    )
    translated_file = service.translate(subtitle_file)
    save_srt(translated_file, output_path)

    if consistency_reviewer is not None and consistency_report_path is not None:
        try:
            review_service = ConsistencyReviewService(
                reviewer=consistency_reviewer,
                source_language=source_language,
                target_language=target_language,
                glossary=glossary,
                chunk_size=review_chunk_size,
                overlap=review_overlap,
            )
            report = review_service.review(subtitle_file, translated_file)
            report_text = render_consistency_report(
                report,
                source_path=input_path,
                translated_path=output_path,
                source_language=source_language,
                target_language=target_language,
                glossary_used=glossary is not None,
            )
            save_consistency_report(report_text, consistency_report_path)
        except (
            ConsistencyProtocolError,
            ConsistencyReviewerError,
            ConsistencyReviewError,
            OSError,
        ) as exc:
            raise ConsistencyReportGenerationError(
                "Translation succeeded, but consistency review failed."
            ) from exc
