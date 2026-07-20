"""Read and write SRT subtitle files."""

from __future__ import annotations

from pathlib import Path

import srt

from .models import Subtitle, SubtitleFile


def load_srt(filename: str | Path) -> SubtitleFile:
    """Load an SRT file."""

    path = Path(filename)

    with path.open("r", encoding="utf-8-sig") as fp:
        content = fp.read()

    subtitles = []

    for item in srt.parse(content):
        subtitles.append(
            Subtitle(
                index=item.index,
                start=item.start,
                end=item.end,
                text=item.content,
            )
        )

    return SubtitleFile(subtitles)


def save_srt(subtitle_file: SubtitleFile, filename: str | Path) -> None:
    """Save an SRT file."""

    output = []

    for subtitle in subtitle_file.subtitles:
        output.append(
            srt.Subtitle(
                index=subtitle.index,
                start=subtitle.start,
                end=subtitle.end,
                content=subtitle.text,
            )
        )

    text = srt.compose(output)

    Path(filename).write_text(text, encoding="utf-8")