"""OpenAI translation provider."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from subtitle_translator.config import load_config
from subtitle_translator.prompts import build_prompt

from .base import TranslationProvider, TranslationRequest


class OpenAIProviderError(RuntimeError):
    """Raised when the OpenAI provider cannot return a translation."""


class OpenAIProvider(TranslationProvider):
    """Translate text using the OpenAI Responses API."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._client = client if client is not None else OpenAI()
        self._model = model if model is not None else load_config().openai_model

    def translate(self, request: TranslationRequest) -> str:
        """Translate text using the configured OpenAI model."""

        response = self._client.responses.create(
            model=self._model,
            instructions=build_prompt(
                source_language=request.source_language,
                target_language=request.target_language,
            ),
            input=request.text,
        )

        if not response.output_text or not response.output_text.strip():
            raise OpenAIProviderError("OpenAI returned an empty translation.")

        return response.output_text
