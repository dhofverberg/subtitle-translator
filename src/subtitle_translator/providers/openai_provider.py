"""OpenAI translation provider."""

from __future__ import annotations

from typing import Any

from openai import OpenAI, OpenAIError

from subtitle_translator.batch import (
    BatchItem,
    BatchProtocolError,
    BatchTranslation,
    parse_batch_response,
    serialize_batch,
)
from subtitle_translator.config import load_config
from subtitle_translator.prompts import build_batch_prompt, build_prompt

from .base import TranslationProvider, TranslationRequest


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
        items: list[BatchItem],
        source_language: str,
        target_language: str,
    ) -> list[BatchTranslation]:
        """Translate a batch using one OpenAI Responses API call."""

        if not items:
            raise ValueError("Translation batch must not be empty.")

        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=build_batch_prompt(
                    source_language=source_language,
                    target_language=target_language,
                ),
                input=serialize_batch(items),
            )
        except OpenAIError as exc:
            raise OpenAIProviderError("OpenAI batch translation request failed.") from exc

        try:
            if not isinstance(response.output_text, str):
                raise BatchProtocolError("Batch response output must be text.")

            return parse_batch_response(response.output_text, items)
        except BatchProtocolError as exc:
            raise OpenAIProviderError(
                f"OpenAI returned an invalid batch translation: {exc}"
            ) from exc
