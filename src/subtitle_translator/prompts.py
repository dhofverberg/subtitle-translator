"""Load and render prompts bundled with Subtitle Translator."""

from __future__ import annotations

from importlib.resources import files

_PROMPT_RESOURCE = files("subtitle_translator").joinpath("resources", "prompt.txt")


def load_prompt_template() -> str:
    """Load the translation prompt template from package resources."""

    return _PROMPT_RESOURCE.read_text(encoding="utf-8")


def build_prompt(source_language: str, target_language: str) -> str:
    """Build a translation prompt for the requested language pair."""

    return load_prompt_template().format(
        source_language=source_language,
        target_language=target_language,
    )
