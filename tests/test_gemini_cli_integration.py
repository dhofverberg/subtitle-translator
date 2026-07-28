from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from typer.testing import CliRunner

from subtitle_translator.cli import app
from subtitle_translator.consistency import ConsistencyReport, ConsistencyReviewRequest
from subtitle_translator.srt import load_srt


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        items = json.loads(kwargs["contents"])["items"]
        translated = [
            {"id": item["id"], "text": f"Översatt: {item['text']}"}
            for item in items
        ]
        return SimpleNamespace(
            prompt_feedback=None,
            candidates=[
                SimpleNamespace(
                    finish_reason="STOP",
                    content=SimpleNamespace(parts=[SimpleNamespace(text=json.dumps(translated))]),
                )
            ],
        )


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class FakeReviewer:
    def __init__(self) -> None:
        self.requests: list[ConsistencyReviewRequest] = []

    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        self.requests.append(request)
        return ConsistencyReport()


def test_cli_gemini_translation_runs_full_srt_pipeline_with_context_and_glossary(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "movie.translated.srt"
    glossary_path = tmp_path / "glossary.json"
    input_path.write_text(
        """10
00:00:01,000 --> 00:00:02,000
Hello
world 👋

30
00:00:03,000 --> 00:00:04,000
The café is open.
""",
        encoding="utf-8",
    )
    glossary_path.write_text(
        '{"source_language": "English", "target_language": "Swedish", '
        '"terms": [{"source": "café", "target": "kafé"}]}',
        encoding="utf-8",
    )
    client = FakeClient()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env-model")
    monkeypatch.setattr(
        "subtitle_translator.providers.gemini_provider.genai.Client",
        lambda *, api_key: client,
    )

    result = CliRunner().invoke(
        app,
        [
            str(input_path),
            "--provider",
            "GEMINI",
            "--output",
            str(output_path),
            "--batch-size",
            "1",
            "--glossary",
            str(glossary_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    translated = load_srt(output_path)
    assert [item.index for item in translated.subtitles] == [10, 30]
    assert [item.text for item in translated.subtitles] == [
        "Översatt: Hello\nworld 👋",
        "Översatt: The café is open.",
    ]
    assert translated.subtitles[0].start.total_seconds() == 1
    assert translated.subtitles[1].end.total_seconds() == 4
    assert client.models.calls[0]["model"] == "gemini-env-model"
    assert json.loads(client.models.calls[1]["contents"])["context"] == [
        {
            "id": 10,
            "source": "Hello\nworld 👋",
            "translation": "Översatt: Hello\nworld 👋",
        }
    ]
    assert json.loads(client.models.calls[0]["contents"])["glossary"]["terms"] == [
        {"source": "café", "target": "kafé"}
    ]


def test_cli_supports_gemini_translation_and_gemini_review(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "movie.translated.srt"
    report_path = tmp_path / "movie.consistency.md"
    input_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    client = FakeClient()
    reviewer = FakeReviewer()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env-model")
    monkeypatch.setattr(
        "subtitle_translator.providers.gemini_provider.genai.Client",
        lambda *, api_key: client,
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.GeminiConsistencyReviewer",
        lambda *, model=None: reviewer,
    )

    result = CliRunner().invoke(
        app,
        [
            str(input_path),
            "--provider",
            "gemini",
            "--output",
            str(output_path),
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert report_path.exists()
    assert len(client.models.calls) == 1
    assert len(reviewer.requests) == 1
    assert [item.id for item in reviewer.requests[0].items] == [1]
