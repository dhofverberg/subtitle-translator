"""OpenAI translation provider."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI, OpenAIError

from subtitle_translator.batch import (
    BatchProtocolError,
    BatchTranslation,
    TranslationContextItem,
    parse_batch_response,
    serialize_batch,
)
from subtitle_translator.config import load_config
from subtitle_translator.glossary import (
    glossary_to_dict,
    validate_glossary_languages,
)
from subtitle_translator.prompts import build_batch_prompt, build_prompt

from .base import BatchTranslationRequest, TranslationProvider, TranslationRequest


class OpenAIProviderError(RuntimeError):
    """Raised when the OpenAI provider cannot return a translation."""


class OpenAIProvider(TranslationProvider):
    """Translate text using the OpenAI Responses API."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        try:
            self._client = client if client is not None else OpenAI()
        except OpenAIError as exc:
            raise OpenAIProviderError("OpenAI client initialization failed.") from exc
        self._model = model if model is not None else load_config().openai_model

    def translate(self, request: TranslationRequest) -> str:
        """Translate text using the configured OpenAI model."""

        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=build_prompt(
                    source_language=request.source_language,
                    target_language=request.target_language,
                ),
                input=request.text,
            )
        except OpenAIError as exc:
            raise OpenAIProviderError("OpenAI translation request failed.") from exc

        if not response.output_text or not response.output_text.strip():
            raise OpenAIProviderError("OpenAI returned an empty translation.")

        return response.output_text

    def translate_batch(
        self,
        request: BatchTranslationRequest,
    ) -> list[BatchTranslation]:
        """Translate a batch using one OpenAI Responses API call."""

        if not request.items:
            raise ValueError("Translation batch must not be empty.")
        if request.glossary is not None:
            validate_glossary_languages(
                request.glossary,
                request.source_language,
                request.target_language,
            )

        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=build_batch_prompt(
                    source_language=request.source_language,
                    target_language=request.target_language,
                ),
                input=_serialize_batch_input(request),
            )
        except OpenAIError as exc:
            raise OpenAIProviderError("OpenAI batch translation request failed.") from exc

        try:
            if not isinstance(response.output_text, str):
                raise BatchProtocolError("Batch response output must be text.")

            return parse_batch_response(response.output_text, list(request.items))
        except BatchProtocolError as exc:
            raise OpenAIProviderError(
                f"OpenAI returned an invalid batch translation: {exc}"
            ) from exc


def _serialize_batch_input(
    request: BatchTranslationRequest,
) -> str:
    if request.glossary is None and request.context is None:
        return serialize_batch(list(request.items))

    payload = {
        "glossary": (
            glossary_to_dict(request.glossary)
            if request.glossary is not None
            else None
        ),
        "context": [
            _context_item_to_dict(item)
            for item in request.context or ()
        ],
        "items": [
            {"id": item.id, "text": item.text}
            for item in request.items
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _context_item_to_dict(item: TranslationContextItem) -> dict[str, int | str]:
    return {
        "id": item.id,
        "source": item.source_text,
        "translation": item.translated_text,
    }
