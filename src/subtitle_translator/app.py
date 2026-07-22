from pathlib import Path

from rich.console import Console

from .providers.base import TranslationProvider
from .srt import load_srt, save_srt
from .subtitle_translation import SubtitleTranslationService

console = Console()


def translate_srt_file(
    input_path: Path,
    output_path: Path,
    provider: TranslationProvider,
    source_language: str,
    target_language: str,
    batch_size: int,
) -> None:
    """Load, translate, and save an SRT subtitle file."""

    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must be different.")

    subtitle_file = load_srt(input_path)
    service = SubtitleTranslationService(
        provider=provider,
        source_language=source_language,
        target_language=target_language,
        batch_size=batch_size,
    )
    translated_file = service.translate(subtitle_file)
    save_srt(translated_file, output_path)


def translate_file(path: Path) -> None:
    """Temporary implementation."""

    console.print()

    console.print("[bold green]Subtitle Translator[/bold green]")

    console.print(f"Input file : {path}")

    console.print()

    console.print("[yellow]Translation engine not implemented yet.[/yellow]")