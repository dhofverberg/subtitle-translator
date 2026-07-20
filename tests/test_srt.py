from pathlib import Path

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