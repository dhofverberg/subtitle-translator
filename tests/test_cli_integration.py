from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from typer.testing import CliRunner

from subtitle_translator.batch import BatchTranslation, TranslationContextItem
from subtitle_translator.cli import app
from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyFinding,
    ConsistencyOccurrence,
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewRequest,
    ConsistencySeverity,
)
from subtitle_translator.providers.base import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationRequest,
)
from subtitle_translator.srt import load_srt


class FakeProvider(TranslationProvider):
    def __init__(self) -> None:
        self.calls: list[BatchTranslationRequest] = []

    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError

    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        self.calls.append(request)
        return [
            BatchTranslation(item.id, f"Översatt: {item.text}")
            for item in request.items
        ]


class FakeReviewer(ConsistencyReviewer):
    def __init__(self) -> None:
        self.requests: list[ConsistencyReviewRequest] = []

    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        self.requests.append(request)
        return ConsistencyReport(
            (
                ConsistencyFinding(
                    severity=ConsistencySeverity.MEDIUM,
                    category=ConsistencyCategory.PERSON_OR_RELATIONSHIP,
                    explanation="Grandmother may use inconsistent relationship terms.",
                    concept="grandmother",
                    variants=("mormor", "farmor"),
                    occurrences=(
                        ConsistencyOccurrence(
                            request.items[0].id,
                            request.items[0].source_text,
                            request.items[0].translated_text,
                        ),
                        ConsistencyOccurrence(
                            request.items[-1].id,
                            request.items[-1].source_text,
                            request.items[-1].translated_text,
                        ),
                    ),
                    manual_check="Confirm the intended family relationship.",
                ),
            )
        )


def test_cli_runs_complete_translation_flow_with_only_provider_replaced(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "translated.srt"
    input_path.write_text(
        """10
00:00:01,250 --> 00:00:03,500
Hello
world

20
00:00:04,000 --> 00:00:06,750
Café 👋
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    models: list[str | None] = []

    def create_provider(*, model: str | None = None) -> FakeProvider:
        models.append(model)
        return provider

    monkeypatch.setattr("subtitle_translator.cli.OpenAIProvider", create_provider)

    result = CliRunner().invoke(
        app,
        [
            str(input_path),
            "--output",
            str(output_path),
            "--source-language",
            "English",
            "--target-language",
            "Swedish",
            "--batch-size",
            "1",
            "--model",
            "integration-model",
        ],
    )

    assert result.exit_code == 0
    assert f"Translation complete: {output_path}" in result.output
    assert models == ["integration-model"]
    assert [[item.id for item in call.items] for call in provider.calls] == [[10], [20]]
    assert [
        (call.source_language, call.target_language)
        for call in provider.calls
    ] == [
        ("English", "Swedish"),
        ("English", "Swedish"),
    ]

    translated = load_srt(output_path)
    assert [subtitle.index for subtitle in translated.subtitles] == [10, 20]
    assert [subtitle.start for subtitle in translated.subtitles] == [
        timedelta(seconds=1, milliseconds=250),
        timedelta(seconds=4),
    ]
    assert [subtitle.end for subtitle in translated.subtitles] == [
        timedelta(seconds=3, milliseconds=500),
        timedelta(seconds=6, milliseconds=750),
    ]
    assert [subtitle.text for subtitle in translated.subtitles] == [
        "Översatt: Hello\nworld",
        "Översatt: Café 👋",
    ]
    assert [call.glossary for call in provider.calls] == [None, None]
    assert provider.calls[0].context == ()
    assert provider.calls[1].context == (
        TranslationContextItem(
            id=10,
            source_text="Hello\nworld",
            translated_text="Översatt: Hello\nworld",
        ),
    )


def test_cli_runs_complete_translation_flow_with_glossary(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "movie.srt"
    output_path = tmp_path / "translated.srt"
    glossary_path = tmp_path / "glossary.json"
    input_path.write_text(
        """10
00:00:01,000 --> 00:00:03,000
Engage the warp drive.

20
00:00:04,000 --> 00:00:06,000
Warp drive ready.
""",
        encoding="utf-8",
    )
    glossary_path.write_text(
        """{
  "source_language": "English",
  "target_language": "Swedish",
  "terms": [{"source": "warp drive", "target": "warpdrift"}]
}""",
        encoding="utf-8",
    )
    provider = FakeProvider()

    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIProvider",
        lambda *, model=None: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            str(input_path),
            "--output",
            str(output_path),
            "--glossary",
            str(glossary_path),
            "--batch-size",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    glossaries = [call.glossary for call in provider.calls]
    assert len(glossaries) == 2
    assert all(glossary is not None for glossary in glossaries)
    assert glossaries[0] == glossaries[1]
    assert glossaries[0].terms[0].target == "warpdrift"
    assert [subtitle.index for subtitle in load_srt(output_path).subtitles] == [10, 20]


def test_cli_integration_generates_translation_and_consistency_report(
    monkeypatch,
    tmp_path: Path,
):
    input_path = tmp_path / "family.srt"
    output_path = tmp_path / "family.translated.srt"
    report_path = tmp_path / "family.consistency.md"
    input_path.write_text(
        """10
00:00:01,000 --> 00:00:02,000
My mother's mother is here.

30
00:00:03,000 --> 00:00:04,000
Grandmother called.

50
00:00:05,000 --> 00:00:06,000
Grandmother will return.
""",
        encoding="utf-8",
    )
    provider = FakeProvider()
    reviewer = FakeReviewer()
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIProvider",
        lambda *, model=None: provider,
    )
    monkeypatch.setattr(
        "subtitle_translator.cli.OpenAIConsistencyReviewer",
        lambda *, model=None: reviewer,
    )

    result = CliRunner().invoke(
        app,
        [
            str(input_path),
            "--output",
            str(output_path),
            "--batch-size",
            "1",
            "--consistency-report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert f"Translation complete: {output_path}" in result.output
    assert f"Consistency report complete: {report_path}" in result.output
    translated = load_srt(output_path)
    assert [subtitle.index for subtitle in translated.subtitles] == [10, 30, 50]
    assert [subtitle.start for subtitle in translated.subtitles] == [
        timedelta(seconds=1),
        timedelta(seconds=3),
        timedelta(seconds=5),
    ]
    assert [subtitle.text for subtitle in translated.subtitles] == [
        "Översatt: My mother's mother is here.",
        "Översatt: Grandmother called.",
        "Översatt: Grandmother will return.",
    ]
    assert len(provider.calls) == 3
    assert len(reviewer.requests) == 1
    assert [item.id for item in reviewer.requests[0].items] == [10, 30, 50]
    assert reviewer.requests[0].items[1].source_text == "Grandmother called."
    assert reviewer.requests[0].items[1].translated_text == (
        "Översatt: Grandmother called."
    )
    report_text = report_path.read_text(encoding="utf-8")
    assert "person_or_relationship" in report_text
    assert "Subtitle IDs: 10, 50" in report_text
    assert "false positives" in report_text
