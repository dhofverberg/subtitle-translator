"""Provider-neutral consistency review models and response validation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .batch import TranslationContextItem
from .glossary import Glossary


class ConsistencyProtocolError(ValueError):
    """Raised when a consistency review response is malformed."""


class ConsistencyReviewerError(RuntimeError):
    """Raised when a consistency reviewer cannot produce a valid report."""


class ConsistencySeverity(StrEnum):
    """Supported consistency finding severity levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConsistencyCategory(StrEnum):
    """Supported consistency finding categories."""

    GLOSSARY_VIOLATION = "glossary_violation"
    TERMINOLOGY = "terminology"
    PERSON_OR_RELATIONSHIP = "person_or_relationship"
    NAME_OR_TITLE = "name_or_title"
    PRONOUN_OR_GENDER = "pronoun_or_gender"
    FORM_OF_ADDRESS = "form_of_address"
    RECURRING_PHRASE = "recurring_phrase"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ConsistencyOccurrence:
    """One accepted subtitle pair cited by a consistency finding."""

    id: int
    source_text: str
    translated_text: str


@dataclass(frozen=True, slots=True)
class ConsistencyFinding:
    """One advisory consistency issue identified for manual review."""

    severity: ConsistencySeverity
    category: ConsistencyCategory
    explanation: str
    concept: str
    variants: tuple[str, ...]
    occurrences: tuple[ConsistencyOccurrence, ...]
    manual_check: str


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    """Validated consistency findings."""

    findings: tuple[ConsistencyFinding, ...] = ()


@dataclass(frozen=True, slots=True)
class ConsistencyReviewRequest:
    """Provider-neutral input for one consistency review chunk."""

    items: tuple[TranslationContextItem, ...]
    source_language: str
    target_language: str
    glossary: Glossary | None = None


class ConsistencyReviewer(ABC):
    """Interface implemented by consistency review providers."""

    @abstractmethod
    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        """Review accepted subtitle pairs without modifying them."""


def parse_consistency_response(
    response_text: str,
    expected_items: tuple[TranslationContextItem, ...],
) -> ConsistencyReport:
    """Parse and strictly validate a consistency review JSON response."""

    try:
        payload: Any = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ConsistencyProtocolError(
            f"Invalid consistency JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise ConsistencyProtocolError("Consistency response must be a JSON object.")
    _validate_fields(payload, {"findings"}, "Consistency response")

    findings_payload = payload["findings"]
    if not isinstance(findings_payload, list):
        raise ConsistencyProtocolError("Consistency field 'findings' must be a list.")

    expected_by_id = {item.id: item for item in expected_items}
    if len(expected_by_id) != len(expected_items):
        raise ConsistencyProtocolError("Expected review items contain duplicate IDs.")

    findings = tuple(
        _parse_finding(item, index, expected_by_id)
        for index, item in enumerate(findings_payload)
    )
    return normalize_consistency_report(ConsistencyReport(findings))


def normalize_consistency_report(report: ConsistencyReport) -> ConsistencyReport:
    """Deterministically deduplicate and sort consistency findings."""

    unique: dict[tuple[object, ...], ConsistencyFinding] = {}
    for finding in report.findings:
        key = (
            finding.category.value,
            finding.concept.strip().casefold(),
            tuple(sorted(variant.strip().casefold() for variant in finding.variants)),
            tuple(sorted(occurrence.id for occurrence in finding.occurrences)),
        )
        unique.setdefault(key, finding)

    severity_order = {
        ConsistencySeverity.HIGH: 0,
        ConsistencySeverity.MEDIUM: 1,
        ConsistencySeverity.LOW: 2,
    }
    findings = sorted(
        unique.values(),
        key=lambda finding: (
            severity_order[finding.severity],
            min(occurrence.id for occurrence in finding.occurrences),
            finding.category.value,
            finding.concept.casefold(),
        ),
    )
    return ConsistencyReport(tuple(findings))


def _parse_finding(
    value: Any,
    index: int,
    expected_by_id: dict[int, TranslationContextItem],
) -> ConsistencyFinding:
    context = f"Finding at index {index}"
    if not isinstance(value, dict):
        raise ConsistencyProtocolError(f"{context} must be a JSON object.")

    _validate_fields(
        value,
        {
            "severity",
            "category",
            "explanation",
            "concept",
            "variants",
            "occurrences",
            "manual_check",
        },
        context,
    )

    severity_text = _non_blank_string(value["severity"], f"{context} severity")
    try:
        severity = ConsistencySeverity(severity_text)
    except ValueError as exc:
        raise ConsistencyProtocolError(
            f"{context} has unknown severity: {severity_text}."
        ) from exc

    category_text = _non_blank_string(value["category"], f"{context} category")
    try:
        category = ConsistencyCategory(category_text)
    except ValueError as exc:
        raise ConsistencyProtocolError(
            f"{context} has unknown category: {category_text}."
        ) from exc

    variants_value = value["variants"]
    if not isinstance(variants_value, list) or not variants_value:
        raise ConsistencyProtocolError(
            f"{context} field 'variants' must be a non-empty list."
        )
    variants = tuple(
        _non_blank_string(variant, f"{context} variant at index {variant_index}")
        for variant_index, variant in enumerate(variants_value)
    )
    normalized_variants = [variant.casefold() for variant in variants]
    if len(normalized_variants) != len(set(normalized_variants)):
        raise ConsistencyProtocolError(f"{context} contains duplicate variants.")

    occurrences_value = value["occurrences"]
    if not isinstance(occurrences_value, list) or not occurrences_value:
        raise ConsistencyProtocolError(
            f"{context} field 'occurrences' must be a non-empty list."
        )
    occurrences = tuple(
        _parse_occurrence(occurrence, index, occurrence_index, expected_by_id)
        for occurrence_index, occurrence in enumerate(occurrences_value)
    )
    occurrence_ids = [occurrence.id for occurrence in occurrences]
    if len(occurrence_ids) != len(set(occurrence_ids)):
        raise ConsistencyProtocolError(f"{context} contains duplicate occurrence IDs.")

    return ConsistencyFinding(
        severity=severity,
        category=category,
        explanation=_non_blank_string(value["explanation"], f"{context} explanation"),
        concept=_non_blank_string(value["concept"], f"{context} concept"),
        variants=variants,
        occurrences=occurrences,
        manual_check=_non_blank_string(value["manual_check"], f"{context} manual_check"),
    )


def _parse_occurrence(
    value: Any,
    finding_index: int,
    occurrence_index: int,
    expected_by_id: dict[int, TranslationContextItem],
) -> ConsistencyOccurrence:
    context = (
        f"Finding at index {finding_index} occurrence at index {occurrence_index}"
    )
    if not isinstance(value, dict):
        raise ConsistencyProtocolError(f"{context} must be a JSON object.")
    _validate_fields(value, {"id", "source", "translation"}, context)

    item_id = value["id"]
    if type(item_id) is not int:
        raise ConsistencyProtocolError(f"{context} field 'id' must be an integer.")
    if item_id not in expected_by_id:
        raise ConsistencyProtocolError(f"{context} has unknown subtitle ID: {item_id}.")

    source = _non_blank_string(value["source"], f"{context} source")
    translation = _non_blank_string(value["translation"], f"{context} translation")
    expected = expected_by_id[item_id]
    if source != expected.source_text:
        raise ConsistencyProtocolError(
            f"{context} source does not match accepted subtitle ID {item_id}."
        )
    if translation != expected.translated_text:
        raise ConsistencyProtocolError(
            f"{context} translation does not match accepted subtitle ID {item_id}."
        )

    return ConsistencyOccurrence(item_id, source, translation)


def _validate_fields(
    value: dict[str, Any],
    expected: set[str],
    context: str,
) -> None:
    missing = expected - value.keys()
    if missing:
        fields = ", ".join(sorted(missing))
        raise ConsistencyProtocolError(f"{context} is missing fields: {fields}.")
    extra = value.keys() - expected
    if extra:
        fields = ", ".join(sorted(str(field) for field in extra))
        raise ConsistencyProtocolError(f"{context} has unexpected fields: {fields}.")


def _non_blank_string(value: Any, context: str) -> str:
    if not isinstance(value, str):
        raise ConsistencyProtocolError(f"{context} must be a string.")
    if not value.strip():
        raise ConsistencyProtocolError(f"{context} must not be blank.")
    return value
