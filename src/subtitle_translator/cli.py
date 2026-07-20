from pathlib import Path

import typer

from .app import translate_file

app = typer.Typer(
    add_completion=False,
    help="AI-powered subtitle translator."
)


@app.command()
def main(
    filename: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Subtitle file (.srt)"
    )
) -> None:
    """Translate a subtitle file."""

    translate_file(filename)