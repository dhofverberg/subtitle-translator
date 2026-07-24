from __future__ import annotations

from pathlib import Path

import pytest
import srt

from subtitle_translator.app import translate_srt_file
from subtitle_translator.batch import BatchTranslation
from subtitle_translator.providers.base import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationRequest,
)
from subtitle_translator.srt import load_srt


class FakeProvider(TranslationProvider):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[BatchTranslationRequest] = []

    def translate(self, request: TranslationRequest) -> str:
        raise NotImplementedError

    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        self.calls.append(request)

        if self.error is not None:
            raise self.error

        return [
            BatchTranslation(id=item.id, text=f"Översatt: {item.text}")
            for item in request.items
        ]


def write_input_srt(path: Path) -> None:
    path.write_text(
        """10
00:00:01,250 --> 00:00:03,500
Hello
world

20
00:00:04,000 --> 00:00:06,750
Café 👋

30
00:00:08,125 --> 00:00:10,000
Goodbye
""",
        encoding="utf-8",
    )


def test_translate_srt_file_end_to_end_with_multiple_batches(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    write_input_srt(input_path)
    original_bytes = input_path.read_bytes()
    original = load_srt(input_path)
    provider = FakeProvider()

    translate_srt_file(
        input_path=input_path,
        output_path=output_path,
        provider=provider,
        source_language="English",
        target_language="Swedish",
        batch_size=2,
    )

    translated = load_srt(output_path)

    assert len(provider.calls) == 2
    assert [[item.id for item in call.items] for call in provider.calls] == [
        [10, 20],
        [30],
    ]
    assert [
        (call.source_language, call.target_language)
        for call in provider.calls
    ] == [
        ("English", "Swedish"),
        ("English", "Swedish"),
    ]
    assert [item.index for item in translated.subtitles] == [10, 20, 30]
    assert [item.start for item in translated.subtitles] == [
        item.start for item in original.subtitles
    ]
    assert [item.end for item in translated.subtitles] == [
        item.end for item in original.subtitles
    ]
    assert [item.text for item in translated.subtitles] == [
        "Översatt: Hello\nworld",
        "Översatt: Café 👋",
        "Översatt: Goodbye",
    ]
    assert input_path.read_bytes() == original_bytes


def test_translate_srt_file_rejects_identical_paths(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    write_input_srt(input_path)
    original_bytes = input_path.read_bytes()
    provider = FakeProvider()

    with pytest.raises(ValueError, match="Input and output paths must be different"):
        translate_srt_file(
            input_path,
            input_path,
            provider,
            "English",
            "Swedish",
            batch_size=2,
        )

    assert input_path.read_bytes() == original_bytes
    assert provider.calls == []


def test_translate_srt_file_does_not_overwrite_existing_output(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    write_input_srt(input_path)
    original_input = input_path.read_bytes()
    output_path.write_text("existing output", encoding="utf-8")
    provider = FakeProvider()

    with pytest.raises(FileExistsError):
        translate_srt_file(
            input_path,
            output_path,
            provider,
            "English",
            "Swedish",
            batch_size=2,
        )

    assert input_path.read_bytes() == original_input
    assert output_path.read_text(encoding="utf-8") == "existing output"


def test_translate_srt_file_propagates_provider_exceptions(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    write_input_srt(input_path)
    error = RuntimeError("Provider failed")

    with pytest.raises(RuntimeError) as exc_info:
        translate_srt_file(
            input_path,
            output_path,
            FakeProvider(error=error),
            "English",
            "Swedish",
            batch_size=2,
        )

    assert exc_info.value is error
    assert not output_path.exists()


def test_translate_srt_file_propagates_malformed_srt_error(tmp_path: Path):
    input_path = tmp_path / "malformed.srt"
    output_path = tmp_path / "output.srt"
    input_path.write_text("this is not an SRT file", encoding="utf-8")
    provider = FakeProvider()

    with pytest.raises(srt.SRTParseError):
        translate_srt_file(
            input_path,
            output_path,
            provider,
            "English",
            "Swedish",
            batch_size=2,
        )

    assert provider.calls == []
    assert not output_path.exists()
