"""JSON protocol for provider-neutral subtitle batch translation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BatchItem:
    """A source text item included in a translation batch."""

    id: int
    text: str


@dataclass(frozen=True, slots=True)
class BatchTranslation:
    """A translated text item returned from a translation batch."""

    id: int
    text: str


@dataclass(frozen=True, slots=True)
class TranslationContextItem:
    """An accepted source/translation pair supplied as read-only context."""

    id: int
    source_text: str
    translated_text: str


class BatchProtocolError(ValueError):
    """Raised when a batch response does not follow the expected protocol."""


def serialize_batch(items: list[BatchItem]) -> str:
    """Serialize batch items to JSON while preserving their order."""

    payload = [{"id": item.id, "text": item.text} for item in items]
    return json.dumps(payload, ensure_ascii=False)


def parse_batch_response(
    response_text: str,
    expected_items: list[BatchItem],
) -> list[BatchTranslation]:
    """Parse and validate translated batch JSON."""

    try:
        payload: Any = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise BatchProtocolError(
            f"Invalid JSON response at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(payload, list):
        raise BatchProtocolError("Batch response must be a JSON list.")

    expected_ids = [item.id for item in expected_items]
    if len(set(expected_ids)) != len(expected_ids):
        raise BatchProtocolError("Expected batch items contain duplicate IDs.")

    if len(payload) != len(expected_items):
        raise BatchProtocolError(
            f"Expected {len(expected_items)} translated items, received {len(payload)}."
        )

    expected_id_set = set(expected_ids)
    translations_by_id: dict[int, BatchTranslation] = {}

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise BatchProtocolError(f"Item at index {index} must be a JSON object.")

        if "id" not in item:
            raise BatchProtocolError(f"Item at index {index} is missing required field 'id'.")
        if "text" not in item:
            raise BatchProtocolError(f"Item at index {index} is missing required field 'text'.")

        extra_fields = set(item) - {"id", "text"}
        if extra_fields:
            fields = ", ".join(sorted(str(field) for field in extra_fields))
            raise BatchProtocolError(f"Item at index {index} has unexpected fields: {fields}.")

        item_id = item["id"]
        text = item["text"]

        if type(item_id) is not int:
            raise BatchProtocolError(f"Item at index {index} field 'id' must be an integer.")
        if not isinstance(text, str):
            raise BatchProtocolError(f"Item at index {index} field 'text' must be a string.")
        if item_id in translations_by_id:
            raise BatchProtocolError(f"Duplicate translation ID: {item_id}.")
        if item_id not in expected_id_set:
            raise BatchProtocolError(f"Unknown translation ID: {item_id}.")
        if not text.strip():
            raise BatchProtocolError(f"Translation text for ID {item_id} must not be blank.")

        translations_by_id[item_id] = BatchTranslation(id=item_id, text=text)

    missing_ids = expected_id_set - translations_by_id.keys()
    if missing_ids:
        ids = ", ".join(str(item_id) for item_id in sorted(missing_ids))
        raise BatchProtocolError(f"Missing translations for IDs: {ids}.")

    return [translations_by_id[item_id] for item_id in expected_ids]
