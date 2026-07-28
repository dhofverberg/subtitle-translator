"""Google Gemini-backed post-translation consistency reviewer."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import errors, types

from subtitle_translator.config import load_config
from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyProtocolError,
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewerError,
    ConsistencyReviewRequest,
    ConsistencySeverity,
    parse_consistency_response,
    serialize_consistency_review_request,
)
from subtitle_translator.glossary import validate_glossary_languages
from subtitle_translator.prompts import build_consistency_prompt

_CONSISTENCY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": [severity.value for severity in ConsistencySeverity],
                    },
                    "category": {
                        "type": "string",
                        "enum": [category.value for category in ConsistencyCategory],
                    },
                    "explanation": {"type": "string"},
                    "concept": {"type": "string"},
                    "variants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "occurrences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "source": {"type": "string"},
                                "translation": {"type": "string"},
                            },
                            "required": ["id", "source", "translation"],
                            "additionalProperties": False,
                        },
                        "minItems": 1,
                    },
                    "manual_check": {"type": "string"},
                },
                "required": [
                    "severity",
                    "category",
                    "explanation",
                    "concept",
                    "variants",
                    "occurrences",
                    "manual_check",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}


class GeminiConsistencyReviewerError(ConsistencyReviewerError):
    """Raised when Gemini cannot produce a valid consistency review."""


class GeminiConsistencyReviewer(ConsistencyReviewer):
    """Review accepted subtitle translations using Gemini generate-content."""

    def __init__(
        self,
        client: Any | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._model = model if model is not None else load_config().gemini_model
        configured_key = api_key if api_key is not None else load_config().gemini_api_key
        if client is not None:
            self._client = client
            return
        if not configured_key:
            raise GeminiConsistencyReviewerError(
                "Gemini API key is not configured. Set GEMINI_API_KEY."
            )
        try:
            self._client = genai.Client(api_key=configured_key)
        except errors.APIError as exc:
            raise GeminiConsistencyReviewerError(
                "Gemini consistency reviewer initialization failed."
            ) from exc

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
            response = self._client.models.generate_content(
                model=self._model,
                contents=serialize_consistency_review_request(request),
                config=types.GenerateContentConfig(
                    systemInstruction=build_consistency_prompt(
                        request.source_language,
                        request.target_language,
                    ),
                    responseMimeType="application/json",
                    responseJsonSchema=_CONSISTENCY_RESPONSE_SCHEMA,
                ),
            )
        except errors.APIError as exc:
            raise GeminiConsistencyReviewerError(
                "Gemini consistency review request failed."
            ) from exc

        try:
            return parse_consistency_response(_response_text(response), request.items)
        except ConsistencyProtocolError as exc:
            raise GeminiConsistencyReviewerError(
                f"Gemini returned an invalid consistency review: {exc}"
            ) from exc


def _response_text(response: Any) -> str:
    if getattr(response, "prompt_feedback", None) is not None:
        raise GeminiConsistencyReviewerError("Gemini blocked the consistency review response.")

    candidates = getattr(response, "candidates", None)
    if not candidates:
        raise GeminiConsistencyReviewerError("Gemini returned an empty consistency review response.")

    candidate = candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    finish_value = getattr(finish_reason, "value", finish_reason)
    if finish_value and finish_value != "STOP":
        if finish_value in {
            "SAFETY",
            "BLOCKLIST",
            "PROHIBITED_CONTENT",
            "SPII",
            "RECITATION",
        }:
            raise GeminiConsistencyReviewerError(
                "Gemini blocked the consistency review response."
            )
        raise GeminiConsistencyReviewerError(
            "Gemini returned an incomplete consistency review response."
        )

    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None)
    if not parts:
        raise GeminiConsistencyReviewerError("Gemini returned an empty consistency review response.")

    text = "".join(
        part.text
        for part in parts
        if isinstance(getattr(part, "text", None), str)
    )
    if not text:
        raise GeminiConsistencyReviewerError("Gemini returned a non-text consistency review response.")
    if not text.strip():
        raise GeminiConsistencyReviewerError("Gemini returned an empty consistency review response.")
    return text
