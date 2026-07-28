from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import srt
from typer.testing import CliRunner

from subtitle_translator.app import (
    ConsistencyReportGenerationError,
    TranslationInputError,
)
from subtitle_translator.batch import BatchProtocolError
from subtitle_translator.cli import app
from subtitle_translator.config import Config
from subtitle_translator.consistency import ConsistencyReport
from subtitle_translator.providers.openai_consistency_reviewer import (
    OpenAIConsistencyReviewerError,
)
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
    assert "Translation complete." in result.output
    assert f"Output: {output_path}" in result.output


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


def test_cli_review_command_appears_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "review" in result.output
    assert "--consistency-report" in result.output


def test_cli_review_command_succeeds_and_reports_no_translation(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "review.md"
    source_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHallo\n", encoding="utf-8")
    reviewer = object()

    def fake_review_srt_files(**kwargs: Any) -> int:
        assert kwargs["source_path"] == source_path
        assert kwargs["translated_path"] == translated_path
        assert kwargs["report_path"] == report_path
        assert callable(kwargs["reviewer"])
        assert kwargs["reviewer"]() is reviewer
        assert kwargs["source_language"] == "English"
        assert kwargs["target_language"] == "Swedish"
        return 2

    monkeypatch.setattr("subtitle_translator.cli.review_srt_files", fake_review_srt_files)
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )

    def create_reviewer(*, model: str | None = None) -> object:
        assert model == "configured-model"
        return reviewer

    monkeypatch.setattr("subtitle_translator.cli.OpenAIConsistencyReviewer", create_reviewer)
    monkeypatch.setattr("subtitle_translator.cli.OpenAIProvider", lambda *, model=None: None)

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--source-language",
            "English",
            "--target-language",
            "Swedish",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "Consistency review complete" in result.output
    assert "No translation was performed" in result.output
    assert "Findings: 2" in result.output


def test_cli_review_rejects_missing_source_file(tmp_path: Path):
    translated_path = tmp_path / "translated.srt"
    translated_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "review",
            str(tmp_path / "missing.srt"),
            str(translated_path),
            "--consistency-report",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code != 0
    assert "Source file does not exist" in result.output


def test_cli_review_rejects_missing_translated_file(tmp_path: Path):
    source_path = tmp_path / "source.srt"
    source_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(tmp_path / "missing-translated.srt"),
            "--consistency-report",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code != 0
    assert "Translated file does not exist" in result.output


def test_cli_review_rejects_existing_report_path(tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    translated_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHej\n", encoding="utf-8")
    report_path.write_text("existing", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "Report file already exists" in result.output
    assert report_path.read_text(encoding="utf-8") == "existing"


def test_cli_review_rejects_incompatible_subtitle_files(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    translated_path.write_text("2\n00:00:01,000 --> 00:00:02,000\nHej\n", encoding="utf-8")

    class CountingReviewer:
        def __init__(self) -> None:
            self.calls = 0

        def review(self, request: Any) -> Any:
            self.calls += 1
            raise AssertionError("review should not be called for invalid subtitle pairs")

    reviewer = CountingReviewer()
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: reviewer,
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "Incompatible subtitle files" in result.output
    assert "Subtitle ID mismatch" in result.output
    assert reviewer.calls == 0
    assert not report_path.exists()


def test_cli_review_forwards_model_override_to_reviewer(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,000 --> 00:00:02,000\nHej\n", encoding="utf-8")
    models: list[str | None] = []

    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )

    class FakeReviewRunner:
        def review(self, request: Any) -> Any:
            return ConsistencyReport()

    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: models.append(model) or FakeReviewRunner(),
    )

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
            "--model",
            "override-model",
        ],
    )

    assert result.exit_code == 0
    assert models == ["override-model"]


def test_cli_review_failures_use_non_zero_exit_code(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,000 --> 00:00:02,000\nHej\n", encoding="utf-8")

    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: (_ for _ in ()).throw(OpenAIConsistencyReviewerError("secret")),
    )

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "Existing translated SRT was not changed" in result.output


def test_cli_review_command_supports_gemini_provider_and_review_model_alias(
    monkeypatch,
    tmp_path: Path,
):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHallo\n", encoding="utf-8")
    created: list[str] = []
    reviewer = object()

    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(
            openai_api_key="sk-test",
            openai_model="openai-model",
            gemini_api_key="gemini-key",
            gemini_model="gemini-model",
            gemini_review_model="gemini-review-model",
        ),
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.GeminiConsistencyReviewer",
        lambda *, model=None: created.append(str(model)) or reviewer,
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.review_srt_files",
        lambda **kwargs: kwargs["reviewer"]() is reviewer and 0,
    )

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--provider",
            "gemini",
            "--review-model",
            "gemini-review-override",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert created == ["gemini-review-override"]
    assert "Provider: gemini Model: gemini-review-override" in result.output


def test_cli_review_rejects_glossary_language_mismatch(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    glossary_path = tmp_path / "glossary.json"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHallo\n", encoding="utf-8")
    glossary_path.write_text(
        json.dumps(
            {
                "source_language": "German",
                "target_language": "Swedish",
                "terms": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
            "--glossary",
            str(glossary_path),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid glossary" in result.output


def test_cli_review_sanitizes_provider_failure(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHello\n", encoding="utf-8")
    translated_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHallo\n", encoding="utf-8")
    secret = "Authorization: ******"
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test", openai_model="configured-model"),
    )

    def fail_reviewer(*, model=None):
        raise OpenAIConsistencyReviewerError(secret)

    monkeypatch.setattr("subtitle_translator.cli.OpenAIConsistencyReviewer", fail_reviewer)

    result = runner.invoke(
        app,
        [
            "review",
            str(source_path),
            str(translated_path),
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code != 0
    assert "Consistency review provider failed" in result.output
    assert secret not in result.output


def test_cli_help_documents_glossary_context_and_consistency_options():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--glossary" in result.output
    assert "--context-size" in result.output
    assert "--consistency-report" in result.output
    assert "--review-provider" in result.output
    assert "--review-model" in result.output


def test_cli_without_report_does_not_construct_reviewer(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)

    def unexpected_reviewer(*, model=None):
        raise AssertionError("reviewer must not be constructed")

    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        unexpected_reviewer,
    )

    result = runner.invoke(app, [str(input_path)])

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["consistency_reviewer"] is None
    assert calls[0]["consistency_report_path"] is None


def test_cli_forwards_report_path_and_resolved_model(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    reviewers: list[tuple[str | None, object]] = []

    def create_reviewer(*, model=None):
        reviewer = object()
        reviewers.append((model, reviewer))
        return reviewer

    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        create_reviewer,
    )

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code == 0
    assert callable(calls[0]["consistency_reviewer"])
    created_reviewer = calls[0]["consistency_reviewer"]()
    assert reviewers[0][0] == "configured-model"
    assert created_reviewer is reviewers[0][1]
    assert calls[0]["consistency_report_path"] == report_path
    assert "Consistency review complete." in result.output
    assert f"Report: {report_path}" in result.output


def test_cli_rejects_existing_report_before_provider_creation(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    report_path.write_text("existing", encoding="utf-8")
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code != 0
    assert "Consistency report already exists" in result.output
    assert providers == []
    assert calls == []
    assert report_path.read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize("same_as", ["input", "output"])
def test_cli_rejects_report_path_equal_to_srt_path(
    monkeypatch,
    tmp_path: Path,
    same_as: str,
):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "movie.translated.srt"
    write_input(input_path)
    report_path = input_path if same_as == "input" else output_path
    providers, calls = install_cli_fakes(monkeypatch)

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code != 0
    assert "Consistency report path must differ" in result.output
    assert providers == []
    assert calls == []


def test_cli_reports_post_translation_review_failure_and_preserves_output(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "movie.translated.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    install_cli_fakes(monkeypatch)
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: object(),
    )

    def fail_after_translation(**kwargs: Any) -> None:
        kwargs["output_path"].write_text("translated", encoding="utf-8")
        raise ConsistencyReportGenerationError("secret request payload")

    monkeypatch.setattr(
        "subtitle_translator.cli.translate_srt_file",
        fail_after_translation,
    )

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code != 0
    assert "Translation succeeded, but consistency review failed" in result.output
    assert "secret request payload" not in result.output
    assert output_path.read_text(encoding="utf-8") == "translated"
    assert not report_path.exists()


def test_cli_sanitizes_reviewer_initialization_errors(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    secret = "Authorization: Bearer sk-review-secret"
    providers, calls = install_cli_fakes(monkeypatch)

    def fail_reviewer(*, model=None):
        raise OpenAIConsistencyReviewerError(secret)

    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        fail_reviewer,
    )
    def invoke_reviewer_then_fail(**kwargs: Any) -> None:
        kwargs["output_path"].write_text("translated", encoding="utf-8")
        reviewer_factory = kwargs["consistency_reviewer"]
        assert callable(reviewer_factory)
        reviewer_factory()

    monkeypatch.setattr(
        "subtitle_translator.cli.translate_srt_file",
        invoke_reviewer_then_fail,
    )

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code != 0
    assert "Consistency review provider failed" in result.output
    assert secret not in result.output
    assert len(providers) == 1
    assert len(calls) == 0


def test_cli_review_provider_defaults_to_translation_provider_when_report_enabled(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    created: list[str] = []

    def create_gemini_reviewer(*, model=None):
        created.append(f"gemini:{model}")
        return object()

    monkeypatch.setattr("subtitle_translator.cli.GeminiConsistencyReviewer", create_gemini_reviewer)
    monkeypatch.setattr("subtitle_translator.cli.GeminiProvider", lambda *, model=None: object())

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--provider",
            "gemini",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    reviewer_factory = calls[0]["consistency_reviewer"]
    assert callable(reviewer_factory)
    reviewer_factory()
    assert created == ["gemini:gemini-2.5-flash"]


def test_cli_review_provider_override_uses_selected_review_provider(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    created: list[str] = []

    monkeypatch.setattr("subtitle_translator.cli.GeminiProvider", lambda *, model=None: object())
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: created.append(f"openai:{model}") or object(),
    )

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--provider",
            "gemini",
            "--review-provider",
            "openai",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    reviewer_factory = calls[0]["consistency_reviewer"]
    assert callable(reviewer_factory)
    reviewer_factory()
    assert created == ["openai:configured-model"]


def test_cli_review_model_explicit_override_wins(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    created: list[str] = []
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: created.append(str(model)) or object(),
    )

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--consistency-report",
            str(report_path),
            "--review-model",
            "review-override",
        ],
    )

    assert result.exit_code == 0
    calls[0]["consistency_reviewer"]()
    assert created == ["review-override"]


def test_cli_uses_openai_review_model_environment_when_set(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(
            openai_api_key="sk-test-key",
            openai_model="openai-normal",
            openai_review_model="openai-review",
            gemini_api_key="gemini-key",
            gemini_model="gemini-normal",
            gemini_review_model="gemini-review",
        ),
    )
    created: list[str] = []
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: created.append(str(model)) or object(),
    )

    result = runner.invoke(
        app,
        [str(input_path), "--consistency-report", str(report_path)],
    )

    assert result.exit_code == 0
    calls[0]["consistency_reviewer"]()
    assert created == ["openai-review"]


def test_cli_uses_gemini_review_model_environment_when_set(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    _, calls = install_cli_fakes(monkeypatch)
    monkeypatch.setattr("subtitle_translator.cli.GeminiProvider", lambda *, model=None: object())
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(
            openai_api_key="sk-test-key",
            openai_model="openai-normal",
            openai_review_model="openai-review",
            gemini_api_key="gemini-key",
            gemini_model="gemini-normal",
            gemini_review_model="gemini-review",
        ),
    )
    created: list[str] = []
    monkeypatch.setattr(
        "subtitle_translator.cli.GeminiConsistencyReviewer",
        lambda *, model=None: created.append(str(model)) or object(),
    )

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--provider",
            "gemini",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    calls[0]["consistency_reviewer"]()
    assert created == ["gemini-review"]


def test_cli_translation_model_and_review_model_are_independent(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    report_path = tmp_path / "movie.consistency.md"
    write_input(input_path)
    providers, calls = install_cli_fakes(monkeypatch)
    created: list[str] = []
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: created.append(str(model)) or object(),
    )

    result = runner.invoke(
        app,
        [
            str(input_path),
            "--model",
            "translation-model",
            "--review-model",
            "review-model",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert providers[0][0] == "translation-model"
    calls[0]["consistency_reviewer"]()
    assert created == ["review-model"]


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
    """KeyboardInterrupt should not be caught by CLI error handlers.
    
    This is tested indirectly - if KeyboardInterrupt is raised in the
    translation function, it should propagate out without being converted
    to a normal error message.
    """
    input_path = tmp_path / "movie.srt"
    write_input(input_path)
    
    # Test that other exceptions ARE caught and converted to error messages
    def fake_translate_srt_file(**kwargs: Any) -> None:
        raise RuntimeError("test error")

    monkeypatch.setattr("subtitle_translator.cli.translate_srt_file", fake_translate_srt_file)
    monkeypatch.setattr(
        "subtitle_translator.cli.load_config",
        lambda: Config(openai_api_key="sk-test-key", openai_model="gpt-4"),
    )
    monkeypatch.setattr("subtitle_translator.cli.OpenAIProvider", lambda model=None: object())

    result = runner.invoke(app, [str(input_path)])

    # RuntimeError should be propagated, not caught by CLI error handlers
    assert result.exception is not None
    assert isinstance(result.exception, RuntimeError)
    # Normal error messages should not appear since this wasn't a handled error
    assert "Translation failed" not in result.output
    assert "Translation provider failed" not in result.output
