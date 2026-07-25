"""Safe atomic text-file persistence helpers."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(
    text: str,
    filename: str | Path,
    *,
    overwrite: bool = False,
) -> None:
    """Atomically write UTF-8 text without overwriting by default."""

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
