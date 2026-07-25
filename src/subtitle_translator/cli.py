from pathlib import Path
from typing import NoReturn

import srt
import typer

from .app import (
    ConsistencyReportGenerationError,
    TranslationInputError,
    translate_srt_file,
)
from .batch import BatchProtocolError
from .config import load_config
from .glossary import GlossaryError, load_glossary
from .providers.openai_consistency_reviewer import (
    OpenAIConsistencyReviewer,
    OpenAIConsistencyReviewerError,
)
from .providers.openai_provider import OpenAIProvider, OpenAIProviderError
from .subtitle_translation import SubtitleTranslationError

DEFAULT_SOURCE_LANGUAGE = "English"
DEFAULT_TARGET_LANGUAGE = "Swedish"
DEFAULT_BATCH_SIZE = 20
DEFAULT_CONTEXT_SIZE = 10

app = typer.Typer(
    add_completion=False,
    help="AI-powered subtitle translator."
)


def _fail(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


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
    glossary_path: Path | None = typer.Option(
        None,
        "--glossary",
        exists=True,
        readable=True,
        file_okay=True,
        dir_okay=False,
        help="UTF-8 JSON glossary file",
    ),
    context_size: int = typer.Option(
        DEFAULT_CONTEXT_SIZE,
        "--context-size",
        help="Maximum previously translated subtitles used as context",
    ),
    consistency_report: Path | None = typer.Option(
        None,
        "--consistency-report",
        help="Write an advisory post-translation Markdown consistency report",
    ),
) -> None:
    """Translate a subtitle file."""

    if batch_size <= 0:
        _fail("batch-size must be greater than zero.")
    if context_size < 0:
        _fail("context-size must not be negative.")

    output_path = output or input_path.with_name(f"{input_path.stem}.translated.srt")

    try:
        if input_path.resolve() == output_path.resolve():
            _fail("Input and output paths must be different.")
        if output_path.exists():
            _fail(f"Output file already exists: {output_path}")
        if consistency_report is not None:
            if consistency_report.resolve() == input_path.resolve():
                _fail("Consistency report path must differ from the input path.")
            if consistency_report.resolve() == output_path.resolve():
                _fail(
                    "Consistency report path must differ from the translated output path."
                )
            if consistency_report.exists():
                _fail(
                    f"Consistency report already exists: {consistency_report}"
                )

        config = load_config()
        glossary = (
            load_glossary(glossary_path, source_language, target_language)
            if glossary_path is not None
            else None
        )
        resolved_model = model or config.openai_model
        provider = OpenAIProvider(model=resolved_model)
        reviewer = (
            OpenAIConsistencyReviewer(model=resolved_model)
            if consistency_report is not None
            else None
        )
        translate_srt_file(
            input_path=input_path,
            output_path=output_path,
            provider=provider,
            source_language=source_language,
            target_language=target_language,
            batch_size=batch_size,
            glossary=glossary,
            context_size=context_size,
            consistency_reviewer=reviewer,
            consistency_report_path=consistency_report,
        )
    except GlossaryError as exc:
        _fail(f"Invalid glossary: {_error_message(exc)}")
    except OpenAIProviderError:
        _fail("Translation provider failed.")
    except OpenAIConsistencyReviewerError:
        _fail("Consistency review provider failed.")
    except ConsistencyReportGenerationError:
        _fail("Translation succeeded, but consistency review failed.")
    except (BatchProtocolError, SubtitleTranslationError) as exc:
        _fail(f"Invalid translation response: {_error_message(exc)}")
    except (srt.SRTParseError, srt.TimestampParseError) as exc:
        _fail(f"Invalid SRT file: {_error_message(exc)}")
    except OSError as exc:
        _fail(f"File operation failed: {_error_message(exc)}")
    except TranslationInputError as exc:
        _fail(f"Invalid input: {_error_message(exc)}")

    typer.echo(f"Translation complete: {output_path}")
    if consistency_report is not None:
        typer.echo(f"Consistency report complete: {consistency_report}")


def _error_message(exc: Exception) -> str:
    return str(exc).strip() or type(exc).__name__
