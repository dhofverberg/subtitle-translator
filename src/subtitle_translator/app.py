from pathlib import Path

from rich.console import Console

console = Console()


def translate_file(path: Path) -> None:
    """Temporary implementation."""

    console.print()

    console.print("[bold green]Subtitle Translator[/bold green]")

    console.print(f"Input file : {path}")

    console.print()

    console.print("[yellow]Translation engine not implemented yet.[/yellow]")