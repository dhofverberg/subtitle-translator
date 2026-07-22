from pathlib import Path

import click
import typer

from .app import translate_srt_file
from .config import Config, load_config
from .providers.openai_provider import OpenAIProvider

DEFAULT_SOURCE_LANGUAGE = "English"
DEFAULT_TARGET_LANGUAGE = "Swedish"
DEFAULT_BATCH_SIZE = 20

app = typer.Typer(
    add_completion=False,
    help="AI-powered subtitle translator."
)


@app.command()
def main(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        file_okay=True,
        dir_okay=False,
        help="Input subtitle file (.srt)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output subtitle file (.srt)",
    ),
    source_language: str = typer.Option(
        DEFAULT_SOURCE_LANGUAGE,
        "--source-language",
        help="Language of the input subtitles",
    ),
    target_language: str = typer.Option(
        DEFAULT_TARGET_LANGUAGE,
        "--target-language",
        help="Language to translate into",
    ),
    batch_size: int = typer.Option(
        DEFAULT_BATCH_SIZE,
        "--batch-size",
        help="Maximum subtitles per translation request",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="OpenAI model override",
    ),
) -> None:
    """Translate a subtitle file."""

    if batch_size <= 0:
        raise click.ClickException("batch-size must be greater than zero.")

    output_path = output or input_path.with_name(f"{input_path.stem}.translated.srt")

    if input_path.resolve() == output_path.resolve():
        raise click.ClickException("Input and output paths must be different.")
    if output_path.exists():
        raise click.ClickException(f"Output file already exists: {output_path}")

    config: Config | None = None

    try:
        config = load_config()
        provider = OpenAIProvider(model=model or config.openai_model)
        translate_srt_file(
            input_path=input_path,
            output_path=output_path,
            provider=provider,
            source_language=source_language,
            target_language=target_language,
            batch_size=batch_size,
        )
    except Exception as exc:
        message = str(exc).strip() or type(exc).__name__
        if config is not None and config.openai_api_key:
            message = message.replace(config.openai_api_key, "[REDACTED]")
        raise click.ClickException(f"Translation failed: {message}") from exc

    typer.echo(f"Translation complete: {output_path}")
