from datetime import timedelta
from pathlib import Path

from subtitle_translator.models import Subtitle, SubtitleFile
from subtitle_translator.srt import load_srt, save_srt


def test_load_simple_file():
    subtitle_file = load_srt("tests/data/simple.srt")

    assert subtitle_file.subtitle_count == 3
    assert subtitle_file.character_count == 27
    assert subtitle_file.word_count == 6


def test_roundtrip(tmp_path: Path):
    original = load_srt("tests/data/simple.srt")

    output = tmp_path / "copy.srt"

    save_srt(original, output)

    loaded = load_srt(output)

    assert loaded.subtitle_count == original.subtitle_count
    assert loaded.character_count == original.character_count
    assert loaded.word_count == original.word_count

    for a, b in zip(original.subtitles, loaded.subtitles):
        assert a.index == b.index
        assert a.start == b.start
        assert a.end == b.end
        assert a.text == b.text


def test_roundtrip_preserves_non_sequential_indices(tmp_path: Path):
    original = SubtitleFile(
        subtitles=[
            Subtitle(10, timedelta(seconds=1), timedelta(seconds=2), "First"),
            Subtitle(20, timedelta(seconds=3), timedelta(seconds=4), "Second\nline"),
            Subtitle(30, timedelta(seconds=5), timedelta(seconds=7), "Third"),
        ]
    )
    output = tmp_path / "non-sequential.srt"

    save_srt(original, output)
    loaded = load_srt(output)

    assert [subtitle.index for subtitle in loaded.subtitles] == [10, 20, 30]

    for expected, actual in zip(original.subtitles, loaded.subtitles, strict=True):
        assert actual.start == expected.start
        assert actual.end == expected.end
        assert actual.text == expected.text
