"""Provider-neutral translation service."""

from __future__ import annotations

from .providers.base import TranslationProvider, TranslationRequest


class Translator:
    """Translate text through a configured translation provider."""

    def __init__(
        self,
        provider: TranslationProvider,
        source_language: str,
        target_language: str,
    ) -> None:
        self._provider = provider
        self._source_language = source_language
        self._target_language = target_language

    def translate_text(self, text: str) -> str:
        """Translate text from the configured source to target language."""

        if not text.strip():
            raise ValueError("Text to translate must not be blank.")

        request = TranslationRequest(
            text=text,
            source_language=self._source_language,
            target_language=self._target_language,
        )
        return self._provider.translate(request)
