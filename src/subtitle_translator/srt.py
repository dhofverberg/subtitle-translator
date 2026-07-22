"""Read and write SRT subtitle files."""

from __future__ import annotations

import os
import tempfile
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

    path = Path(filename)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(text)
            temporary_path = Path(temporary_file.name)

        if overwrite:
            os.replace(temporary_path, path)
        else:
            os.link(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
