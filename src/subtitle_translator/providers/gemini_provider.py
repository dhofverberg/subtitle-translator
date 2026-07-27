"""Google Gemini translation provider."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import errors, types

from subtitle_translator.batch import BatchProtocolError, BatchTranslation, parse_batch_response
from subtitle_translator.config import load_config
from subtitle_translator.glossary import validate_glossary_languages
from subtitle_translator.prompts import build_batch_prompt, build_prompt

from .base import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationProviderError,
    TranslationRequest,
    serialize_batch_request,
)

_BATCH_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "text": {"type": "string"},
        },
        "required": ["id", "text"],
        "additionalProperties": False,
    },
}


class GeminiProviderError(TranslationProviderError):
    """Raised when Gemini cannot return a valid translation."""


class GeminiProvider(TranslationProvider):
    """Translate text using Gemini's stateless generate-content API."""

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
            raise GeminiProviderError("Gemini API key is not configured. Set GEMINI_API_KEY.")
        try:
            self._client = genai.Client(api_key=configured_key)
        except errors.APIError as exc:
            raise GeminiProviderError("Gemini client initialization failed.") from exc

    def translate(self, request: TranslationRequest) -> str:
        """Translate one text item with Gemini."""

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=request.text,
                config=types.GenerateContentConfig(
                    systemInstruction=build_prompt(
                        request.source_language,
                        request.target_language,
                    ),
                ),
            )
        except errors.APIError as exc:
            raise GeminiProviderError("Gemini translation request failed.") from exc
        return _response_text(response)

    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        """Translate a subtitle batch with Gemini JSON Schema output."""

        if not request.items:
            raise ValueError("Translation batch must not be empty.")
        if request.glossary is not None:
            validate_glossary_languages(
                request.glossary,
                request.source_language,
                request.target_language,
            )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=serialize_batch_request(request, always_structured=True),
                config=types.GenerateContentConfig(
                    systemInstruction=build_batch_prompt(
                        request.source_language,
                        request.target_language,
                    ),
                    responseMimeType="application/json",
                    responseJsonSchema=_BATCH_RESPONSE_SCHEMA,
                ),
            )
        except errors.APIError as exc:
            raise GeminiProviderError("Gemini batch translation request failed.") from exc

        try:
            return parse_batch_response(_response_text(response), list(request.items))
        except BatchProtocolError as exc:
            raise GeminiProviderError(
                f"Gemini returned an invalid batch translation: {exc}"
            ) from exc


def _response_text(response: Any) -> str:
    """Extract text without relying on the SDK convenience ``response.text`` property."""

    if getattr(response, "prompt_feedback", None) is not None:
        raise GeminiProviderError("Gemini blocked the translation response.")

    candidates = getattr(response, "candidates", None)
    if not candidates:
        raise GeminiProviderError("Gemini returned an empty translation response.")

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
            raise GeminiProviderError("Gemini blocked the translation response.")
        raise GeminiProviderError("Gemini returned an incomplete translation response.")

    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None)
    if not parts:
        raise GeminiProviderError("Gemini returned an empty translation response.")

    text = "".join(
        part.text
        for part in parts
        if isinstance(getattr(part, "text", None), str)
    )
    if not text.strip():
        raise GeminiProviderError("Gemini returned an empty translation response.")
    return text
