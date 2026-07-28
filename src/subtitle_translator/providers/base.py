"""Base interfaces for translation providers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from subtitle_translator.batch import (
    BatchItem,
    BatchTranslation,
    TranslationContextItem,
)
from subtitle_translator.glossary import Glossary, glossary_to_dict


class TranslationProviderError(RuntimeError):
    """Raised when a translation provider cannot produce a translation."""


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Input passed to a translation provider."""

    text: str
    source_language: str
    target_language: str


@dataclass(frozen=True, slots=True)
class BatchTranslationRequest:
    """Provider-neutral input for one subtitle translation batch."""

    items: tuple[BatchItem, ...]
    source_language: str
    target_language: str
    glossary: Glossary | None = None
    context: tuple[TranslationContextItem, ...] | None = None

    def __post_init__(self) -> None:
        item_ids = {item.id for item in self.items}
        context_ids = [item.id for item in self.context or ()]

        if len(context_ids) != len(set(context_ids)):
            raise ValueError("Translation context must not contain duplicate IDs.")

        overlapping_ids = item_ids.intersection(context_ids)
        if overlapping_ids:
            ids = ", ".join(str(item_id) for item_id in sorted(overlapping_ids))
            raise ValueError(
                "Translation context IDs must not overlap current batch IDs: "
                f"{ids}."
            )


class TranslationProvider(ABC):
    """Interface implemented by translation providers."""

    @abstractmethod
    def translate(self, request: TranslationRequest) -> str:
        """Translate the supplied request and return the translated text."""

    @abstractmethod
    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        """Translate a batch of text items and return their translations."""


def serialize_batch_request(
    request: BatchTranslationRequest,
    *,
    always_structured: bool = False,
) -> str:
    """Serialize batch data while keeping glossary, context, and items separate."""

    if not always_structured and request.glossary is None and request.context is None:
        payload: object = [{"id": item.id, "text": item.text} for item in request.items]
    else:
        payload = {
            "glossary": (
                glossary_to_dict(request.glossary)
                if request.glossary is not None
                else None
            ),
            "context": [
                {
                    "id": item.id,
                    "source": item.source_text,
                    "translation": item.translated_text,
                }
                for item in request.context or ()
            ],
            "items": [{"id": item.id, "text": item.text} for item in request.items],
        }
    return json.dumps(payload, ensure_ascii=False)
