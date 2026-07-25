"""OpenAI-backed post-translation consistency reviewer."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI, OpenAIError

from subtitle_translator.config import load_config
from subtitle_translator.consistency import (
    ConsistencyProtocolError,
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewerError,
    ConsistencyReviewRequest,
    parse_consistency_response,
)
from subtitle_translator.glossary import glossary_to_dict, validate_glossary_languages
from subtitle_translator.prompts import build_consistency_prompt


class OpenAIConsistencyReviewerError(ConsistencyReviewerError):
    """Raised when OpenAI cannot produce a valid consistency review."""


class OpenAIConsistencyReviewer(ConsistencyReviewer):
    """Review accepted subtitle translations using the Responses API."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        try:
            self._client = client if client is not None else OpenAI()
        except OpenAIError as exc:
            raise OpenAIConsistencyReviewerError(
                "OpenAI consistency reviewer initialization failed."
            ) from exc
        self._model = model if model is not None else load_config().openai_model

    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        """Review one chunk without changing any subtitle text."""

        if not request.items:
            raise ValueError("Consistency review items must not be empty.")
        if request.glossary is not None:
            validate_glossary_languages(
                request.glossary,
                request.source_language,
                request.target_language,
            )

        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=build_consistency_prompt(
                    request.source_language,
                    request.target_language,
                ),
                input=_serialize_consistency_request(request),
            )
        except OpenAIError as exc:
            raise OpenAIConsistencyReviewerError(
                "OpenAI consistency review request failed."
            ) from exc

        try:
            if not isinstance(response.output_text, str):
                raise ConsistencyProtocolError(
                    "Consistency response output must be text."
                )
            return parse_consistency_response(response.output_text, request.items)
        except ConsistencyProtocolError as exc:
            raise OpenAIConsistencyReviewerError(
                f"OpenAI returned an invalid consistency review: {exc}"
            ) from exc


def _serialize_consistency_request(request: ConsistencyReviewRequest) -> str:
    payload = {
        "source_language": request.source_language,
        "target_language": request.target_language,
        "glossary": (
            glossary_to_dict(request.glossary)
            if request.glossary is not None
            else None
        ),
        "subtitle_pairs": [
            {
                "id": item.id,
                "source": item.source_text,
                "translation": item.translated_text,
            }
            for item in request.items
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
