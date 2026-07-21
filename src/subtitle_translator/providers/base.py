"""Base interfaces for translation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Input passed to a translation provider."""

    text: str
    source_language: str
    target_language: str


class TranslationProvider(ABC):
    """Interface implemented by translation providers."""

    @abstractmethod
    def translate(self, request: TranslationRequest) -> str:
        """Translate the supplied request and return the translated text."""
