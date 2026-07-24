from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from typer.testing import CliRunner

from subtitle_translator.batch import BatchTranslation, TranslationContextItem
from subtitle_translator.cli import app
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
