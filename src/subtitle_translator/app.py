from pathlib import Path

from .consistency import (
    ConsistencyProtocolError,
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewerError,
)
from .consistency_report import render_consistency_report, save_consistency_report
from .consistency_review import ConsistencyReviewError, ConsistencyReviewService
from .glossary import Glossary
from .models import SubtitleFile
from .providers.base import TranslationProvider
from .srt import load_srt, save_srt
from .subtitle_translation import SubtitleTranslationService


class TranslationInputError(ValueError):
    """Raised when application translation inputs are invalid."""


class ConsistencyReportGenerationError(RuntimeError):
    """Raised when review fails after the translated SRT was saved."""


class SubtitlePairValidationError(ValueError):
    """Raised when source and translated subtitles are incompatible."""


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
            _write_consistency_report(
                source_file=subtitle_file,
                translated_file=translated_file,
                report_path=consistency_report_path,
                reviewer=consistency_reviewer,
                source_language=source_language,
                target_language=target_language,
                glossary=glossary,
                source_path=input_path,
                translated_path=output_path,
                review_chunk_size=review_chunk_size,
                review_overlap=review_overlap,
            )
        except (
            ConsistencyProtocolError,
            ConsistencyReviewerError,
            ConsistencyReviewError,
            OSError,
        ) as exc:
            raise ConsistencyReportGenerationError(
                "Translation succeeded, but consistency review failed."
            ) from exc


def _write_consistency_report(
    *,
    source_file: SubtitleFile,
    translated_file: SubtitleFile,
    report_path: Path,
    reviewer: ConsistencyReviewer,
    source_language: str,
    target_language: str,
    glossary: Glossary | None,
    source_path: Path,
    translated_path: Path,
    review_chunk_size: int,
    review_overlap: int,
) -> ConsistencyReport:
    review_service = ConsistencyReviewService(
        reviewer=reviewer,
        source_language=source_language,
        target_language=target_language,
        glossary=glossary,
        chunk_size=review_chunk_size,
        overlap=review_overlap,
    )
    report = review_service.review(source_file, translated_file)
    report_text = render_consistency_report(
        report,
        source_path=source_path,
        translated_path=translated_path,
        source_language=source_language,
        target_language=target_language,
        glossary_used=glossary is not None,
    )
    save_consistency_report(report_text, report_path)
    return report


def review_srt_files(
    source_path: Path,
    translated_path: Path,
    report_path: Path,
    reviewer: ConsistencyReviewer,
    source_language: str,
    target_language: str,
    glossary: Glossary | None = None,
    review_chunk_size: int = 100,
    review_overlap: int = 10,
) -> int:
    """Review and compare existing source and translated SRT files."""

    if source_path.resolve() == translated_path.resolve():
        raise SubtitlePairValidationError(
            "Source and translated paths must be different."
        )

    report_path_resolved = report_path.resolve()
    if report_path_resolved == source_path.resolve():
        raise SubtitlePairValidationError(
            "Report path must differ from the source path."
        )
    if report_path_resolved == translated_path.resolve():
        raise SubtitlePairValidationError(
            "Report path must differ from the translated path."
        )
    if report_path.exists():
        raise FileExistsError(f"Report file already exists: {report_path}")

    source_file = load_srt(source_path)
    translated_file = load_srt(translated_path)

    _validate_subtitle_pairs(source_file, translated_file)

    try:
        report = _write_consistency_report(
            source_file=source_file,
            translated_file=translated_file,
            report_path=report_path,
            reviewer=reviewer,
            source_language=source_language,
            target_language=target_language,
            glossary=glossary,
            source_path=source_path,
            translated_path=translated_path,
            review_chunk_size=review_chunk_size,
            review_overlap=review_overlap,
        )
    except (
        ConsistencyProtocolError,
        ConsistencyReviewerError,
        ConsistencyReviewError,
        OSError,
    ) as exc:
        raise ConsistencyReportGenerationError(
            "Consistency review failed."
        ) from exc

    return len(report.findings)


def _validate_subtitle_pairs(
    source_file: SubtitleFile,
    translated_file: SubtitleFile,
) -> None:
    """Validate that source and translated subtitles are compatible for review."""

    if len(source_file.subtitles) != len(translated_file.subtitles):
        raise SubtitlePairValidationError(
            f"Subtitle count mismatch: source has {len(source_file.subtitles)}, "
            f"translated has {len(translated_file.subtitles)}."
        )

    source_indices = {}
    for position, subtitle in enumerate(source_file.subtitles):
        idx = subtitle.index
        if idx in source_indices:
            raise SubtitlePairValidationError(
                f"Duplicate subtitle index in source: {idx} at positions "
                f"{source_indices[idx]} and {position}."
            )
        source_indices[idx] = position

    translated_indices = {}
    for position, subtitle in enumerate(translated_file.subtitles):
        idx = subtitle.index
        if idx in translated_indices:
            raise SubtitlePairValidationError(
                f"Duplicate subtitle index in translated: {idx} at positions "
                f"{translated_indices[idx]} and {position}."
            )
        translated_indices[idx] = position

    for position, (source, translated) in enumerate(
        zip(source_file.subtitles, translated_file.subtitles, strict=True)
    ):
        if source.index != translated.index:
            raise SubtitlePairValidationError(
                f"Subtitle ID mismatch at position {position}: "
                f"source {source.index} != translated {translated.index}."
            )
        if source.start != translated.start:
            raise SubtitlePairValidationError(
                f"Start timestamp mismatch at subtitle {source.index}: "
                f"source {source.start} != translated {translated.start}."
            )
        if source.end != translated.end:
            raise SubtitlePairValidationError(
                f"End timestamp mismatch at subtitle {source.index}: "
                f"source {source.end} != translated {translated.end}."
            )
