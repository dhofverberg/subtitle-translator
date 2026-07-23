"""Provider-neutral glossary models and JSON loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GlossaryError(ValueError):
    """Raised when glossary data is invalid."""


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    """An approved source-to-target terminology pair."""

    source: str
    target: str


@dataclass(frozen=True, slots=True)
class Glossary:
    """Validated terminology for one translation language pair."""

    source_language: str
    target_language: str
    terms: tuple[GlossaryTerm, ...]


def load_glossary(
    filename: str | Path,
    source_language: str,
    target_language: str,
) -> Glossary:
    """Load and validate a UTF-8 glossary JSON file."""

    try:
        text = Path(filename).read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise GlossaryError("Glossary file must contain valid UTF-8 text.") from exc

    return parse_glossary(text, source_language, target_language)


def parse_glossary(
    text: str,
    source_language: str,
    target_language: str,
) -> Glossary:
    """Parse and validate glossary JSON for a requested language pair."""

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GlossaryError(
            f"Invalid glossary JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise GlossaryError("Glossary must be a JSON object.")

    _validate_fields(
        payload,
        required={"source_language", "target_language", "terms"},
        context="Glossary",
    )

    declared_source = _non_blank_string(
        payload["source_language"],
        "Glossary field 'source_language'",
    )
    declared_target = _non_blank_string(
        payload["target_language"],
        "Glossary field 'target_language'",
    )

    terms_payload = payload["terms"]
    if not isinstance(terms_payload, list):
        raise GlossaryError("Glossary field 'terms' must be a JSON list.")

    terms: list[GlossaryTerm] = []
    normalized_sources: set[str] = set()

    for index, term_payload in enumerate(terms_payload):
        if not isinstance(term_payload, dict):
            raise GlossaryError(f"Glossary term at index {index} must be a JSON object.")

        _validate_fields(
            term_payload,
            required={"source", "target"},
            context=f"Glossary term at index {index}",
        )
        source = _non_blank_string(
            term_payload["source"],
            f"Glossary term at index {index} field 'source'",
        )
        target = _non_blank_string(
            term_payload["target"],
            f"Glossary term at index {index} field 'target'",
        )

        normalized_source = source.casefold()
        if normalized_source in normalized_sources:
            raise GlossaryError(
                f"Duplicate glossary source term at index {index}."
            )

        normalized_sources.add(normalized_source)
        terms.append(GlossaryTerm(source=source, target=target))

    glossary = Glossary(
        source_language=declared_source,
        target_language=declared_target,
        terms=tuple(terms),
    )
    validate_glossary_languages(glossary, source_language, target_language)
    return glossary


def validate_glossary_languages(
    glossary: Glossary,
    source_language: str,
    target_language: str,
) -> None:
    """Ensure a glossary matches the requested translation languages."""

    if glossary.source_language.casefold() != source_language.strip().casefold():
        raise GlossaryError(
            "Glossary source language does not match the requested source language."
        )
    if glossary.target_language.casefold() != target_language.strip().casefold():
        raise GlossaryError(
            "Glossary target language does not match the requested target language."
        )


def glossary_to_dict(glossary: Glossary) -> dict[str, object]:
    """Convert a validated glossary to JSON-compatible data."""

    return {
        "source_language": glossary.source_language,
        "target_language": glossary.target_language,
        "terms": [
            {"source": term.source, "target": term.target}
            for term in glossary.terms
        ],
    }


def _validate_fields(
    payload: dict[str, Any],
    *,
    required: set[str],
    context: str,
) -> None:
    missing = required - payload.keys()
    if missing:
        fields = ", ".join(repr(field) for field in sorted(missing))
        raise GlossaryError(f"{context} is missing required field(s): {fields}.")

    extra = payload.keys() - required
    if extra:
        fields = ", ".join(repr(field) for field in sorted(extra))
        raise GlossaryError(f"{context} has unexpected field(s): {fields}.")


def _non_blank_string(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise GlossaryError(f"{context} must be a string.")

    stripped = value.strip()
    if not stripped:
        raise GlossaryError(f"{context} must not be blank.")

    return stripped
