"""Composition helpers for optional translation providers."""

from __future__ import annotations

from typing import Any

from subtitle_translator.config import Config, load_config

from .base import TranslationProvider

SUPPORTED_TRANSLATION_PROVIDERS = ("openai", "gemini")


class TranslationProviderConfigurationError(RuntimeError):
    """Raised when a selected translation provider cannot be configured."""


def normalize_provider_name(provider_name: str) -> str:
    """Normalize and validate a translation provider name."""

    normalized = provider_name.strip().casefold()
    if normalized not in SUPPORTED_TRANSLATION_PROVIDERS:
        choices = ", ".join(SUPPORTED_TRANSLATION_PROVIDERS)
        raise TranslationProviderConfigurationError(
            f"Unknown translation provider: {provider_name!r}. Choose one of: {choices}."
        )
    return normalized


def create_translation_provider(
    provider_name: str,
    *,
    model: str | None = None,
    config: Config | None = None,
    client: Any | None = None,
) -> TranslationProvider:
    """Construct the selected translation provider without eager SDK imports."""

    normalized = normalize_provider_name(provider_name)
    resolved_config = config or load_config()

    if normalized == "openai":
        try:
            from .openai_provider import OpenAIProvider
        except ModuleNotFoundError as exc:
            if exc.name != "openai":
                raise
            raise TranslationProviderConfigurationError(
                "OpenAI support is not installed. Install subtitle-translator[openai]."
            ) from exc

        return OpenAIProvider(client=client, model=model or resolved_config.openai_model)

    if not resolved_config.gemini_api_key:
        raise TranslationProviderConfigurationError(
            "Gemini API key is not configured. Set GEMINI_API_KEY."
        )

    try:
        from .gemini_provider import GeminiProvider
    except ModuleNotFoundError as exc:
        if exc.name not in {"google", "google.genai"}:
            raise
        raise TranslationProviderConfigurationError(
            "Gemini support is not installed. Install subtitle-translator[gemini]."
        ) from exc

    return GeminiProvider(
        client=client,
        model=model or resolved_config.gemini_model,
        api_key=resolved_config.gemini_api_key,
    )


def create_openai_consistency_reviewer(
    *,
    model: str | None = None,
    config: Config | None = None,
    client: Any | None = None,
) -> Any:
    """Construct the OpenAI-only consistency reviewer lazily."""

    try:
        from .openai_consistency_reviewer import OpenAIConsistencyReviewer
    except ModuleNotFoundError as exc:
        if exc.name != "openai":
            raise
        raise TranslationProviderConfigurationError(
            "OpenAI support is not installed. Install subtitle-translator[openai]."
        ) from exc

    resolved_config = config or load_config()
    return OpenAIConsistencyReviewer(client=client, model=model or resolved_config.openai_model)
