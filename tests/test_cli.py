from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import srt
from typer.testing import CliRunner

from subtitle_translator.app import TranslationInputError
from subtitle_translator.batch import BatchProtocolError
from subtitle_translator.cli import app
from subtitle_translator.config import Config
from subtitle_translator.providers.openai_provider import OpenAIProviderError
from subtitle_translator.subtitle_translation import SubtitleTranslationError

runner = CliRunner()


def write_input(path: Path) -> None:
    path.write_text(
        """1
00:00:01,000 --> 00:00:02,000
Hello
""",
        encoding="utf-8",
    )


def install_cli_fakes(
    monkeypatch,
    *,
    error: BaseException | None = None,
    api_key: str = "sk-test-secret",
):
    providers: list[tuple[str | None, object]] = []
    calls: list[dict[str, Any]] = []

    def create_provider(*, model: str | None = None) -> object:
        provider = object()
        providers.append((model, provider))
        return provider

    def fake_translate_srt_file(**kwargs: Any) -> None:
        calls.append(kwargs)
        if error is not None:
            raise error
        kwargs["output_path"].write_text("translated", encoding="utf-8")

    monkeypatch.setattr("subtitle_translator.cli.OpenAIProvider", create_provider)
    monkeypatch.setattr("subtitle_translator.cli.translate_srt_file", fake_translate_srt_file)
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key=api_key, openai_model="configured-model"),
    )
    return providers, calls


def test_cli_requires_input_path():
    result = runner.invoke(app, [])

    assert result.exit_code != 0
    assert "Missing argument" in result.output


def test_cli_rejects_missing_input_file(tmp_path: Path):
    result = runner.invoke(app, [str(tmp_path / "missing.srt")])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_cli_uses_explicit_output_and_shows_success(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "custom.srt"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert calls[0]["input_path"] == input_path
    assert calls[0]["output_path"] == output_path
    assert calls[0]["context_size"] == 10
    assert f"Translation complete: {output_path}" in result.output


def test_cli_derives_safe_output_path(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code == 0
    assert calls[0]["output_path"] == tmp_path / "movie.translated.srt"
    assert calls[0]["output_path"] != input_path
    assert providers[0][0] == "configured-model"


def test_cli_forwards_languages_batch_size_and_model(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--source-language",
            "German",
            "--target-language",
            "Swedish",
            "--batch-size",
            "7",
            "--model",
            "override-model",
            "--context-size",
            "4",
        ],
    )

    assert result.exit_code == 0
    assert providers[0][0] == "override-model"
    assert calls[0]["provider"] is providers[0][1]
    assert calls[0]["source_language"] == "German"
    assert calls[0]["target_language"] == "Swedish"
    assert calls[0]["batch_size"] == 7
    assert calls[0]["context_size"] == 4
    assert calls[0]["glossary"] is None


def test_cli_loads_and_forwards_valid_glossary(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    glossary_path = tmp_path / "glossary.json"
    write_input(input_path)
    glossary_path.write_text(
        json.dumps(
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [
                    {"source": "warp drive", "target": "warpdrift"},
                ],
            }
        ),
        encoding="utf-8",
    )
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--glossary", str(glossary_path)],
    )

    assert result.exit_code == 0
    assert len(providers) == 1
    assert calls[0]["glossary"].source_language == "English"
    assert calls[0]["glossary"].target_language == "Swedish"
    assert calls[0]["glossary"].terms[0].source == "warp drive"
    assert calls[0]["glossary"].terms[0].target == "warpdrift"


def test_cli_rejects_missing_glossary_file_before_provider_creation(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--glossary", str(tmp_path / "missing.json")],
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert providers == []
    assert calls == []


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("{not JSON", "Invalid glossary JSON"),
        (
            json.dumps(
                {
                    "source_language": "German",
                    "target_language": "Swedish",
                    "terms": [],
                }
            ),
            "source language",
        ),
        (
            json.dumps(
                {
                    "source_language": "English",
                    "target_language": "Swedish",
                    "terms": [
                        {"source": "Warp Drive", "target": "warpdrift"},
                        {"source": " warp drive ", "target": "annan term"},
                    ],
                }
            ),
            "Duplicate glossary source term",
        ),
    ],
    ids=["invalid-json", "language-mismatch", "duplicate-source"],
)
def test_cli_rejects_invalid_glossary_before_provider_request(
    monkeypatch,
    tmp_path: Path,
    payload: str,
    message: str,
):
    input_path = tmp_path / "movie.srt"
    glossary_path = tmp_path / "glossary.json"
    write_input(input_path)
    glossary_path.write_text(payload, encoding="utf-8")
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--glossary", str(glossary_path)],
    )

    assert result.exit_code != 0
    assert "Invalid glossary" in result.output
    assert message in result.output
    assert providers == []
    assert calls == []


def test_cli_help_documents_glossary_and_context_options():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--glossary" in result.output
    assert "--context-size" in result.output


def test_cli_rejects_invalid_batch_size_before_translation(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path), "--batch-size", "0"])

    assert result.exit_code != 0
    assert "batch-size must be greater than zero" in result.output
    assert providers == []
    assert calls == []


def test_cli_allows_context_size_zero(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path), "--context-size", "0"])

    assert result.exit_code == 0
    assert len(providers) == 1
    assert calls[0]["context_size"] == 0


def test_cli_rejects_negative_context_size_before_provider_creation(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path), "--context-size", "-1"])

    assert result.exit_code != 0
    assert "context-size must not be negative" in result.output
    assert providers == []
    assert calls == []


def test_cli_rejects_existing_derived_output(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "movie.translated.srt"
    write_input(input_path)
    output_path.write_text("existing", encoding="utf-8")
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert "Output file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing"
    assert providers == []
    assert calls == []


def test_cli_rejects_identical_input_and_output(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    original = input_path.read_bytes()
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(app, [str(input_path), "-o", str(input_path)])

    assert result.exit_code != 0
    assert "Input and output paths must be different" in result.output
    assert input_path.read_bytes() == original
    assert providers == []
    assert calls == []


def test_cli_reports_provider_creation_errors_without_details(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    secret = "sk-provider-secret"
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key=secret, openai_model="configured-model"),
    )

    def fail_provider(*, model: str | None = None) -> object:
        raise OpenAIProviderError(
            f"Authorization: Bearer {secret}; complete configuration follows"
        )

    monkeypatch.setattr("subtitle_translator.cli.OpenAIProvider", fail_provider)

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert "Translation provider failed" in result.output
    assert secret not in result.output
    assert "Authorization" not in result.output
    assert "configuration" not in result.output


def test_cli_hides_sensitive_provider_application_errors(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    secret = "sk-super-secret-value"
    _, calls = install_cli_fakes(
        monkeypatch,
        error=OpenAIProviderError(f"Authorization: Bearer {secret}"),
        api_key=secret,
    )

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert "Translation provider failed" in result.output
    assert secret not in result.output
    assert "Authorization" not in result.output
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (PermissionError("access denied"), "File operation failed: access denied"),
        (
            srt.SRTParseError(1, 2, "malformed subtitle"),
            "Invalid SRT file:",
        ),
        (
            srt.TimestampParseError("invalid timestamp"),
            "Invalid SRT file: invalid timestamp",
        ),
        (
            BatchProtocolError("invalid JSON"),
            "Invalid translation response: invalid JSON",
        ),
        (
            SubtitleTranslationError("missing translation ID"),
            "Invalid translation response: missing translation ID",
        ),
        (
            TranslationInputError("invalid language"),
            "Invalid input: invalid language",
        ),
    ],
    ids=[
        "filesystem",
        "srt-parsing",
        "srt-serialization",
        "batch-protocol",
        "translation-contract",
        "input-validation",
    ],
)
def test_cli_reports_expected_application_errors(
    monkeypatch,
    tmp_path: Path,
    error: Exception,
    expected_message: str,
):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch, error=error)

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert expected_message in result.output
    assert len(calls) == 1


@pytest.mark.parametrize(
    "error",
    [RuntimeError("runtime defect"), ValueError("value defect")],
    ids=["runtime-error", "value-error"],
)
def test_cli_does_not_rewrite_unexpected_programming_errors(
    monkeypatch,
    tmp_path: Path,
    error: Exception,
):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    install_cli_fakes(monkeypatch, error=error)

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert result.exception is error
    assert "Translation failed" not in result.output
    assert str(error) not in result.output


def test_cli_does_not_catch_keyboard_interrupt(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    install_cli_fakes(monkeypatch, error=KeyboardInterrupt())

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code != 0
    assert "Translation failed" not in result.output
    assert "Translation provider failed" not in result.output
