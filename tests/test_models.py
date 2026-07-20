from datetime import timedelta

from subtitle_translator.models import Subtitle, SubtitleFile


def test_subtitle_duration():
    subtitle = Subtitle(
        index=1,
        start=timedelta(seconds=5),
        end=timedelta(seconds=8),
        text="Hello",
    )

    assert subtitle.duration == timedelta(seconds=3)


def test_subtitle_character_count():
    subtitle = Subtitle(
        index=1,
        start=timedelta(),
        end=timedelta(seconds=1),
        text="Hello world",
    )

    assert subtitle.character_count == 11


def test_subtitle_line_count():
    subtitle = Subtitle(
        index=1,
        start=timedelta(),
        end=timedelta(seconds=1),
        text="Line one\nLine two",
    )

    assert subtitle.line_count == 2


def test_subtitle_file_statistics():
    file = SubtitleFile(
        subtitles=[
            Subtitle(
                1,
                timedelta(seconds=0),
                timedelta(seconds=2),
                "Hello world",
            ),
            Subtitle(
                2,
                timedelta(seconds=3),
                timedelta(seconds=5),
                "Another subtitle",
            ),
        ]
    )

    assert file.subtitle_count == 2
    assert file.character_count == 27
    assert file.word_count == 4
    assert file.duration == timedelta(seconds=5)