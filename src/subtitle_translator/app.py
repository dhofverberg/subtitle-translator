from pathlib import Path

from .glossary import Glossary
from .providers.base import TranslationProvider
from .srt import load_srt, save_srt
from .subtitle_translation import SubtitleTranslationService


class TranslationInputError(ValueError):
    """Raised when application translation inputs are invalid."""


def translate_srt_file(
    input_path: Path,
    output_path: Path,
    provider: TranslationProvider,
    source_language: str,
    target_language: str,
    batch_size: int,
    glossary: Glossary | None = None,
) -> None:
    """Load, translate, and save an SRT subtitle file."""

    if input_path.resolve() == output_path.resolve():
        raise TranslationInputError("Input and output paths must be different.")

    subtitle_file = load_srt(input_path)
    service = SubtitleTranslationService(
        provider=provider,
        source_language=source_language,
        target_language=target_language,
        batch_size=batch_size,
        glossary=glossary,
    )
    translated_file = service.translate(subtitle_file)
    save_srt(translated_file, output_path)
