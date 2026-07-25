"""Read and write SRT subtitle files."""

from __future__ import annotations

from pathlib import Path

import srt

from .models import Subtitle, SubtitleFile
from .persistence import write_text_atomic


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


def save_srt(
    subtitle_file: SubtitleFile,
    filename: str | Path,
    *,
    overwrite: bool = False,
) -> None:
    """Save an SRT file without overwriting an existing file by default."""

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

    text = srt.compose(output, reindex=False)

    write_text_atomic(text, filename, overwrite=overwrite)
