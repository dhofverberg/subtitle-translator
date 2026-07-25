"""Load and render prompts bundled with Subtitle Translator."""

from __future__ import annotations

from importlib.resources import files

_PROMPT_RESOURCE = files("subtitle_translator").joinpath("resources", "prompt.txt")
_BATCH_PROMPT_RESOURCE = files("subtitle_translator").joinpath(
    "resources", "batch_prompt.txt"
)
_CONSISTENCY_PROMPT_RESOURCE = files("subtitle_translator").joinpath(
    "resources", "consistency_prompt.txt"
)


def load_prompt_template() -> str:
    """Load the translation prompt template from package resources."""

    return _PROMPT_RESOURCE.read_text(encoding="utf-8")


def build_prompt(source_language: str, target_language: str) -> str:
    """Build a translation prompt for the requested language pair."""

    return load_prompt_template().format(
        source_language=source_language,
        target_language=target_language,
    )


def load_batch_prompt_template() -> str:
    """Load the batch translation prompt template from package resources."""

    return _BATCH_PROMPT_RESOURCE.read_text(encoding="utf-8")


def build_batch_prompt(source_language: str, target_language: str) -> str:
    """Build a batch translation prompt for the requested language pair."""

    return load_batch_prompt_template().format(
        source_language=source_language,
        target_language=target_language,
    )


def load_consistency_prompt_template() -> str:
    """Load the consistency review prompt template from package resources."""

    return _CONSISTENCY_PROMPT_RESOURCE.read_text(encoding="utf-8")


def build_consistency_prompt(source_language: str, target_language: str) -> str:
    """Build a consistency review prompt for the requested language pair."""

    return load_consistency_prompt_template().format(
        source_language=source_language,
        target_language=target_language,
    )
