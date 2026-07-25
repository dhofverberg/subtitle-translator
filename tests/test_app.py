from __future__ import annotations

from pathlib import Path

import pytest
import srt

from subtitle_translator.app import (
    ConsistencyReportGenerationError,
    SubtitlePairValidationError,
    review_srt_files,
    translate_srt_file,
)
from subtitle_translator.batch import BatchTranslation
from subtitle_translator.consistency import (
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewerError,
    ConsistencyReviewRequest,
)
from subtitle_translator.glossary import Glossary, GlossaryTerm
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


class FakeReviewer(ConsistencyReviewer):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[ConsistencyReviewRequest] = []

    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ConsistencyReport()


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


def test_translate_srt_file_generates_advisory_report_after_translation(
    tmp_path: Path,
):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    report_path = tmp_path / "consistency.md"
    write_input_srt(input_path)
    reviewer = FakeReviewer()
    glossary = Glossary(
        "English",
        "Swedish",
        (GlossaryTerm("grandmother", "mormor"),),
    )

    translate_srt_file(
        input_path,
        output_path,
        FakeProvider(),
        "English",
        "Swedish",
        batch_size=2,
        glossary=glossary,
        consistency_reviewer=reviewer,
        consistency_report_path=report_path,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert "No likely consistency issues were identified." in report_path.read_text(
        encoding="utf-8"
    )
    assert len(reviewer.requests) == 1
    assert reviewer.requests[0].glossary == glossary
    assert [item.id for item in reviewer.requests[0].items] == [10, 20, 30]
    assert reviewer.requests[0].items[0].source_text == "Hello\nworld"
    assert reviewer.requests[0].items[0].translated_text == "Översatt: Hello\nworld"


def test_existing_report_is_rejected_before_translation_provider_call(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    report_path = tmp_path / "consistency.md"
    write_input_srt(input_path)
    report_path.write_text("existing report", encoding="utf-8")
    provider = FakeProvider()
    reviewer = FakeReviewer()

    with pytest.raises(FileExistsError, match="Consistency report already exists"):
        translate_srt_file(
            input_path,
            output_path,
            provider,
            "English",
            "Swedish",
            batch_size=2,
            consistency_reviewer=reviewer,
            consistency_report_path=report_path,
        )

    assert provider.calls == []
    assert reviewer.requests == []
    assert not output_path.exists()
    assert report_path.read_text(encoding="utf-8") == "existing report"


@pytest.mark.parametrize("same_as", ["input", "output"])
def test_report_path_must_differ_from_srt_paths(tmp_path: Path, same_as: str):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    write_input_srt(input_path)
    report_path = input_path if same_as == "input" else output_path
    provider = FakeProvider()

    with pytest.raises(ValueError, match="Consistency report path must differ"):
        translate_srt_file(
            input_path,
            output_path,
            provider,
            "English",
            "Swedish",
            batch_size=2,
            consistency_reviewer=FakeReviewer(),
            consistency_report_path=report_path,
        )

    assert provider.calls == []
    assert not output_path.exists()


def test_translation_failure_creates_neither_output_nor_report(tmp_path: Path):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    report_path = tmp_path / "consistency.md"
    write_input_srt(input_path)

    with pytest.raises(RuntimeError, match="translation failed"):
        translate_srt_file(
            input_path,
            output_path,
            FakeProvider(error=RuntimeError("translation failed")),
            "English",
            "Swedish",
            batch_size=2,
            consistency_reviewer=FakeReviewer(),
            consistency_report_path=report_path,
        )

    assert not output_path.exists()
    assert not report_path.exists()


def test_review_failure_preserves_completed_translation_without_partial_report(
    tmp_path: Path,
):
    input_path = tmp_path / "input.srt"
    output_path = tmp_path / "output.srt"
    report_path = tmp_path / "consistency.md"
    write_input_srt(input_path)
    error = ConsistencyReviewerError("Authorization: Bearer secret")

    with pytest.raises(
        ConsistencyReportGenerationError,
        match="Translation succeeded, but consistency review failed",
    ) as exc_info:
        translate_srt_file(
            input_path,
            output_path,
            FakeProvider(),
            "English",
            "Swedish",
            batch_size=2,
            consistency_reviewer=FakeReviewer(error),
            consistency_report_path=report_path,
        )

    assert exc_info.value.__cause__ is error
    assert output_path.exists()
    assert [item.index for item in load_srt(output_path).subtitles] == [10, 20, 30]
    assert not report_path.exists()


def test_review_srt_files_generates_report_and_pairs_subtitles(tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text(
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
    translated_path.write_text(
        """10
00:00:01,250 --> 00:00:03,500
Hallo
welt

20
00:00:04,000 --> 00:00:06,750
Café 👋
""",
        encoding="utf-8",
    )
    reviewer = FakeReviewer()
    glossary = Glossary(
        "English",
        "Swedish",
        (GlossaryTerm("grandmother", "mormor"),),
    )

    finding_count = review_srt_files(
        source_path=source_path,
        translated_path=translated_path,
        report_path=report_path,
        reviewer=reviewer,
        source_language="English",
        target_language="Swedish",
        glossary=glossary,
    )

    assert finding_count == 0
    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8").startswith(
        "# Subtitle Translation Consistency Report"
    )
    assert len(reviewer.requests) == 1
    assert reviewer.requests[0].glossary == glossary
    assert [item.id for item in reviewer.requests[0].items] == [10, 20]
    assert reviewer.requests[0].items[0].source_text == "Hello\nworld"
    assert reviewer.requests[0].items[0].translated_text == "Hallo\nwelt"


def test_review_srt_files_rejects_subtitle_count_mismatch(tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text(
        """10
00:00:01,250 --> 00:00:03,500
Hello
""",
        encoding="utf-8",
    )
    translated_path.write_text(
        """10
00:00:01,250 --> 00:00:03,500
Hello

20
00:00:04,000 --> 00:00:06,750
Hi
""",
        encoding="utf-8",
    )
    reviewer = FakeReviewer()

    with pytest.raises(SubtitlePairValidationError, match="Subtitle count mismatch"):
        review_srt_files(
            source_path=source_path,
            translated_path=translated_path,
            report_path=report_path,
            reviewer=reviewer,
            source_language="English",
            target_language="Swedish",
        )

    assert reviewer.requests == []
    assert not report_path.exists()


def test_review_srt_files_does_not_modify_existing_files(tmp_path: Path):
    source_path = tmp_path / "source.srt"
    translated_path = tmp_path / "translated.srt"
    report_path = tmp_path / "report.md"
    source_path.write_text("10\n00:00:01,250 --> 00:00:03,500\nHello\n", encoding="utf-8")
    translated_path.write_text(
        "10\n00:00:01,250 --> 00:00:03,500\nHallo\n",
        encoding="utf-8",
    )
    reviewer = FakeReviewer()
    source_bytes = source_path.read_bytes()
    translated_bytes = translated_path.read_bytes()

    review_srt_files(
        source_path=source_path,
        translated_path=translated_path,
        report_path=report_path,
        reviewer=reviewer,
        source_language="English",
        target_language="Swedish",
    )

    assert source_path.read_bytes() == source_bytes
    assert translated_path.read_bytes() == translated_bytes
