import sys
from pathlib import Path
from typing import NoReturn

import click
import srt
import typer.testing
from typer.testing import _get_command as _typer_get_command

from .app import (
    ConsistencyReportGenerationError,
    SubtitlePairValidationError,
    TranslationInputError,
    review_srt_files,
    translate_srt_file,
)
from .batch import BatchProtocolError
from .config import load_config
from .consistency import ConsistencyReviewerError
from .glossary import GlossaryError, load_glossary
from .providers.base import TranslationProviderError
from .providers.factory import (
    TranslationProviderConfigurationError,
    create_consistency_reviewer,
    create_openai_consistency_reviewer,
    create_translation_provider,
    normalize_provider_name,
    normalize_review_provider_name,
    resolve_review_model,
    resolve_translation_model,
)
from .subtitle_translation import SubtitleTranslationError

DEFAULT_SOURCE_LANGUAGE = "English"
DEFAULT_TARGET_LANGUAGE = "Swedish"
DEFAULT_BATCH_SIZE = 20
DEFAULT_CONTEXT_SIZE = 10


def OpenAIProvider(*, model: str | None = None) -> object:
    """Construct the default provider lazily for legacy CLI test seams."""

    return create_translation_provider("openai", model=model)


def GeminiProvider(*, model: str | None = None) -> object:
    """Construct the Gemini provider lazily."""

    return create_translation_provider("gemini", model=model)


def OpenAIConsistencyReviewer(*, model: str | None = None) -> object:
    """Construct the OpenAI-only reviewer lazily for legacy CLI test seams."""

    return create_openai_consistency_reviewer(model=model)


def GeminiConsistencyReviewer(*, model: str | None = None) -> object:
    """Construct the Gemini-only reviewer lazily for CLI test seams."""

    return create_consistency_reviewer("gemini", model=model)


class LegacyCompatibleGroup(click.Group):
    def main(
        self,
        args: list[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: object,
    ) -> int:
        if args is None:
            args = sys.argv[1:]
        args = list(args)

        # If first arg is a command or an option, use normal Click parsing
        if args and (args[0] in self.commands or args[0].startswith("-")):
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=standalone_mode,
                **extra,
            )

        # Legacy mode or no args: parse as legacy translation input
        try:
            parsed = _parse_legacy_args(tuple(args))
        except click.UsageError as exc:
            click.echo(f"Error: {exc.format_message()}", err=True)
            if standalone_mode:
                sys.exit(2)
            return 2

        _run_translate_command(
            input_path=parsed["input_path"],
            output=parsed.get("output"),
            source_language=parsed.get("source_language", DEFAULT_SOURCE_LANGUAGE),
            target_language=parsed.get("target_language", DEFAULT_TARGET_LANGUAGE),
            batch_size=parsed.get("batch_size", DEFAULT_BATCH_SIZE),
            model=parsed.get("model"),
            review_model=parsed.get("review_model"),
            provider_name=parsed.get("provider_name", "openai"),
            review_provider_name=parsed.get("review_provider_name"),
            glossary_path=parsed.get("glossary_path"),
            context_size=parsed.get("context_size", DEFAULT_CONTEXT_SIZE),
            consistency_report=parsed.get("consistency_report"),
        )
        return 0


def _get_click_command_for_compat(app_obj: object) -> click.Command:
    if getattr(app_obj, "_subtitle_translator_cli", False):
        return app_obj
    return _typer_get_command(app_obj)


typer.testing._get_command = _get_click_command_for_compat


@click.group(
    cls=LegacyCompatibleGroup,
    invoke_without_command=False,
    no_args_is_help=False,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
@click.option("--output", "-o", type=click.Path(path_type=Path, exists=False))
@click.option("--source-language", default=DEFAULT_SOURCE_LANGUAGE)
@click.option("--target-language", default=DEFAULT_TARGET_LANGUAGE)
@click.option("--batch-size", default=DEFAULT_BATCH_SIZE, type=int)
@click.option("--model")
@click.option("--review-model")
@click.option(
    "--provider",
    "provider_name",
    type=click.Choice(["openai", "gemini"], case_sensitive=False),
    default="openai",
    show_default=True,
)
@click.option(
    "--review-provider",
    "review_provider_name",
    type=click.Choice(["openai", "gemini"], case_sensitive=False),
)
@click.option(
    "--glossary",
    type=click.Path(path_type=Path, exists=True, readable=True, file_okay=True, dir_okay=False),
)
@click.option("--context-size", default=DEFAULT_CONTEXT_SIZE, type=int)
@click.option("--consistency-report", type=click.Path(path_type=Path, exists=False))
def app(
    output: Path | None,
    source_language: str,
    target_language: str,
    batch_size: int,
    model: str | None,
    review_model: str | None,
    provider_name: str,
    review_provider_name: str | None,
    glossary: Path | None,
    context_size: int,
    consistency_report: Path | None,
) -> None:
    """AI-powered subtitle translator."""


@app.command("translate")
@click.argument("input_path", type=click.Path(path_type=Path, exists=False))
@click.option("--output", "-o", type=click.Path(path_type=Path, exists=False))
@click.option("--source-language", default=DEFAULT_SOURCE_LANGUAGE)
@click.option("--target-language", default=DEFAULT_TARGET_LANGUAGE)
@click.option("--batch-size", default=DEFAULT_BATCH_SIZE, type=int)
@click.option("--model")
@click.option("--review-model")
@click.option(
    "--provider",
    "provider_name",
    type=click.Choice(["openai", "gemini"], case_sensitive=False),
    default="openai",
    show_default=True,
)
@click.option(
    "--review-provider",
    "review_provider_name",
    type=click.Choice(["openai", "gemini"], case_sensitive=False),
)
@click.option(
    "--glossary",
    type=click.Path(path_type=Path, exists=True, readable=True, file_okay=True, dir_okay=False),
)
@click.option("--context-size", default=DEFAULT_CONTEXT_SIZE, type=int)
@click.option("--consistency-report", type=click.Path(path_type=Path, exists=False))
def translate_command(
    input_path: Path,
    output: Path | None,
    source_language: str,
    target_language: str,
    batch_size: int,
    model: str | None,
    review_model: str | None,
    provider_name: str,
    review_provider_name: str | None,
    glossary: Path | None,
    context_size: int,
    consistency_report: Path | None,
) -> None:
    """Translate a subtitle file."""

    _run_translate_command(
        input_path=input_path,
        output=output,
        source_language=source_language,
        target_language=target_language,
        batch_size=batch_size,
        model=model,
        review_model=review_model,
        provider_name=provider_name,
        review_provider_name=review_provider_name,
        glossary_path=glossary,
        context_size=context_size,
        consistency_report=consistency_report,
    )


@app.command(name="review")
@click.argument("source_srt", type=click.Path(path_type=Path, exists=False))
@click.argument("translated_srt", type=click.Path(path_type=Path, exists=False))
@click.option("--source-language", default=DEFAULT_SOURCE_LANGUAGE)
@click.option("--target-language", default=DEFAULT_TARGET_LANGUAGE)
@click.option(
    "--provider",
    "provider_name",
    type=click.Choice(["openai", "gemini"], case_sensitive=False),
    default="openai",
    show_default=True,
)
@click.option("--consistency-report", required=True, type=click.Path(path_type=Path, exists=False))
@click.option("--model", "review_model")
@click.option("--review-model", "review_model")
@click.option(
    "--glossary",
    type=click.Path(path_type=Path, exists=True, readable=True, file_okay=True, dir_okay=False),
)
def review_command(
    source_srt: Path,
    translated_srt: Path,
    source_language: str,
    target_language: str,
    provider_name: str,
    consistency_report: Path,
    review_model: str | None,
    glossary: Path | None,
) -> None:
    """Review existing subtitle files for consistency issues."""

    normalized_provider = normalize_review_provider_name(provider_name)

    try:
        if not source_srt.exists():
            _fail(f"Source file does not exist: {source_srt}")
        if not translated_srt.exists():
            _fail(f"Translated file does not exist: {translated_srt}")

        config = load_config()
        glossary_value = (
            load_glossary(glossary, source_language, target_language)
            if glossary is not None
            else None
        )
        resolved_model = resolve_review_model(
            normalized_provider,
            model=review_model,
            config=config,
        )

        finding_count = review_srt_files(
            source_path=source_srt,
            translated_path=translated_srt,
            report_path=consistency_report,
            reviewer=lambda: _create_consistency_reviewer(
                normalized_provider,
                resolved_model,
            ),
            source_language=source_language,
            target_language=target_language,
            glossary=glossary_value,
        )
    except GlossaryError as exc:
        _fail(f"Invalid glossary: {_error_message(exc)}")
    except FileExistsError as exc:
        _fail(_error_message(exc))
    except ConsistencyReviewerError:
        _fail(
            "Consistency review provider failed "
            f"({normalized_provider}). Existing translated SRT was not changed."
        )
    except ConsistencyReportGenerationError as exc:
        _fail(
            f"{_error_message(exc)} ({normalized_provider}). "
            "Existing translated SRT was not changed."
        )
    except SubtitlePairValidationError as exc:
        _fail(f"Incompatible subtitle files: {_error_message(exc)}")
    except (srt.SRTParseError, srt.TimestampParseError) as exc:
        _fail(f"Invalid SRT file: {_error_message(exc)}")
    except OSError as exc:
        _fail(f"File operation failed: {_error_message(exc)}")

    click.echo(
        "Consistency review complete. "
        f"Provider: {normalized_provider} Model: {resolved_model}. "
        f"No translation was performed. Source: {source_srt} "
        f"Translated: {translated_srt} Report: {consistency_report} "
        f"Findings: {finding_count}."
    )


app._subtitle_translator_cli = True


def _convert_path(path_str: str, exists: bool = False, readable: bool = False) -> Path:
    path = Path(path_str)
    if exists and not path.exists():
        raise click.BadParameter(f"Path '{path_str}' does not exist.")
    if readable and not path.is_file():
        raise click.BadParameter(f"Path '{path_str}' is not a readable file.")
    return path


def _parse_legacy_args(args: tuple[str, ...]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    index = 0
    while index < len(args):
        token = args[index]
        if token in {"--output", "-o"}:
            if index + 1 >= len(args):
                raise click.UsageError("Option '--output' requires a value.")
            parsed["output"] = _convert_path(args[index + 1], exists=False)
            index += 2
        elif token == "--source-language":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--source-language' requires a value.")
            parsed["source_language"] = args[index + 1]
            index += 2
        elif token == "--target-language":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--target-language' requires a value.")
            parsed["target_language"] = args[index + 1]
            index += 2
        elif token == "--batch-size":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--batch-size' requires a value.")
            parsed["batch_size"] = int(args[index + 1])
            index += 2
        elif token == "--model":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--model' requires a value.")
            parsed["model"] = args[index + 1]
            index += 2
        elif token == "--review-model":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--review-model' requires a value.")
            parsed["review_model"] = args[index + 1]
            index += 2
        elif token == "--provider":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--provider' requires a value.")
            parsed["provider_name"] = args[index + 1]
            index += 2
        elif token == "--review-provider":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--review-provider' requires a value.")
            parsed["review_provider_name"] = args[index + 1]
            index += 2
        elif token == "--glossary":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--glossary' requires a value.")
            parsed["glossary_path"] = _convert_path(
                args[index + 1],
                exists=True,
                readable=True,
            )
            index += 2
        elif token == "--context-size":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--context-size' requires a value.")
            parsed["context_size"] = int(args[index + 1])
            index += 2
        elif token == "--consistency-report":
            if index + 1 >= len(args):
                raise click.UsageError("Option '--consistency-report' requires a value.")
            parsed["consistency_report"] = _convert_path(args[index + 1], exists=False)
            index += 2
        elif token.startswith("--"):
            raise click.UsageError(f"No such option: {token}")
        else:
            if "input_path" in parsed:
                raise click.UsageError(f"Got unexpected argument: {token}")
            parsed["input_path"] = Path(token)
            index += 1

    if "input_path" not in parsed:
        raise click.UsageError("Missing argument 'INPUT_PATH'.")

    return parsed


def _run_translate_command(
    *,
    input_path: Path,
    output: Path | None,
    source_language: str,
    target_language: str,
    batch_size: int,
    model: str | None,
    review_model: str | None,
    provider_name: str = "openai",
    review_provider_name: str | None,
    glossary_path: Path | None,
    context_size: int,
    consistency_report: Path | None,
) -> None:
    try:
        normalized_provider = normalize_provider_name(provider_name)
    except TranslationProviderConfigurationError as exc:
        _fail(_error_message(exc))

    if batch_size <= 0:
        _fail("batch-size must be greater than zero.")
    if context_size < 0:
        _fail("context-size must not be negative.")

    if not input_path.exists():
        _fail(f"Input file does not exist: {input_path}")

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
                _fail(f"Consistency report already exists: {consistency_report}")

        config = load_config()
        resolved_translation_model = resolve_translation_model(
            normalized_provider,
            model=model,
            config=config,
        )
        glossary = (
            load_glossary(glossary_path, source_language, target_language)
            if glossary_path is not None
            else None
        )
        provider = (
            OpenAIProvider(model=resolved_translation_model)
            if normalized_provider == "openai"
            else GeminiProvider(model=resolved_translation_model)
        )
        resolved_review_provider: str | None = None
        resolved_review_model: str | None = None
        reviewer = None
        if consistency_report is not None:
            resolved_review_provider = normalize_review_provider_name(
                review_provider_name or normalized_provider
            )
            resolved_review_model = resolve_review_model(
                resolved_review_provider,
                model=review_model,
                config=config,
            )

            def reviewer_factory() -> object:
                return _create_consistency_reviewer(
                    resolved_review_provider,
                    resolved_review_model,
                )

            reviewer = reviewer_factory

        finding_count = translate_srt_file(
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
    except FileExistsError as exc:
        _fail(_error_message(exc))
    except (TranslationProviderError, TranslationProviderConfigurationError):
        _fail("Translation provider failed.")
    except ConsistencyReviewerError:
        _fail("Consistency review provider failed.")
    except ConsistencyReportGenerationError as exc:
        review_label = normalize_review_provider_name(review_provider_name or normalized_provider)
        if "writing" in _error_message(exc).casefold():
            _fail(
                "Translation succeeded, but consistency report writing failed "
                f"({review_label}). Translated SRT was preserved."
            )
        _fail(
            "Translation succeeded, but consistency review failed "
            f"({review_label}). Translated SRT was preserved."
        )
    except (BatchProtocolError, SubtitleTranslationError) as exc:
        _fail(f"Invalid translation response: {_error_message(exc)}")
    except (srt.SRTParseError, srt.TimestampParseError) as exc:
        _fail(f"Invalid SRT file: {_error_message(exc)}")
    except OSError as exc:
        _fail(f"File operation failed: {_error_message(exc)}")
    except TranslationInputError as exc:
        _fail(f"Invalid input: {_error_message(exc)}")

    click.echo(
        "Translation complete. "
        f"Provider: {normalized_provider} Model: {resolved_translation_model}. "
        f"Output: {output_path}"
    )
    if consistency_report is not None:
        click.echo(
            "Consistency review complete. "
            f"Provider: {resolved_review_provider} Model: {resolved_review_model}. "
            f"Report: {consistency_report} Findings: {finding_count}."
        )


def _create_consistency_reviewer(provider_name: str, model: str) -> object:
    try:
        if provider_name == "openai":
            return OpenAIConsistencyReviewer(model=model)
        return GeminiConsistencyReviewer(model=model)
    except TranslationProviderConfigurationError as exc:
        raise ConsistencyReviewerError(_error_message(exc)) from exc


def _fail(message: str) -> NoReturn:
    click.echo(f"Error: {message}", err=True)
    raise SystemExit(1)


def _error_message(exc: Exception) -> str:
    return str(exc).strip() or type(exc).__name__
