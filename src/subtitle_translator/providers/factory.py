"""Composition helpers for optional translation providers."""

from __future__ import annotations

from typing import Any

from subtitle_translator.config import Config, load_config

from .base import TranslationProvider

SUPPORTED_TRANSLATION_PROVIDERS = ("openai", "gemini")
SUPPORTED_REVIEW_PROVIDERS = ("openai", "gemini")


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


def normalize_review_provider_name(provider_name: str) -> str:
    """Normalize and validate a consistency review provider name."""

    normalized = provider_name.strip().casefold()
    if normalized not in SUPPORTED_REVIEW_PROVIDERS:
        choices = ", ".join(SUPPORTED_REVIEW_PROVIDERS)
        raise TranslationProviderConfigurationError(
            f"Unknown review provider: {provider_name!r}. Choose one of: {choices}."
        )
    return normalized


def resolve_translation_model(
    provider_name: str,
    *,
    model: str | None = None,
    config: Config | None = None,
) -> str:
    """Resolve a translation model for the selected provider."""

    normalized = normalize_provider_name(provider_name)
    resolved_config = config or load_config()
    openai_model = resolved_config.openai_model
    gemini_model = resolved_config.gemini_model
    if normalized == "openai":
        return model or openai_model
    return model or gemini_model


def resolve_review_model(
    provider_name: str,
    *,
    model: str | None = None,
    config: Config | None = None,
) -> str:
    """Resolve a review model for the selected provider."""

    normalized = normalize_review_provider_name(provider_name)
    resolved_config = config or load_config()
    openai_model = resolved_config.openai_model
    gemini_model = resolved_config.gemini_model
    openai_review_model = getattr(resolved_config, "openai_review_model", None)
    gemini_review_model = getattr(resolved_config, "gemini_review_model", None)
    if normalized == "openai":
        return model or openai_review_model or openai_model
    return model or gemini_review_model or gemini_model


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
    resolved_model = resolve_translation_model(
        normalized,
        model=model,
        config=resolved_config,
    )

    if normalized == "openai":
        try:
            from .openai_provider import OpenAIProvider
        except ModuleNotFoundError as exc:
            if exc.name != "openai":
                raise
            raise TranslationProviderConfigurationError(
                "OpenAI support is not installed. Install subtitle-translator[openai]."
            ) from exc

        return OpenAIProvider(client=client, model=resolved_model)

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
        model=resolved_model,
        api_key=resolved_config.gemini_api_key,
    )


def create_openai_consistency_reviewer(
    *,
    model: str | None = None,
    config: Config | None = None,
    client: Any | None = None,
) -> Any:
    """Construct the OpenAI-only consistency reviewer lazily."""

    return create_consistency_reviewer(
        "openai",
        model=model,
        config=config,
        client=client,
    )


def create_consistency_reviewer(
    provider_name: str,
    *,
    model: str | None = None,
    config: Config | None = None,
    client: Any | None = None,
) -> Any:
    """Construct the selected consistency reviewer lazily."""

    normalized = normalize_review_provider_name(provider_name)
    resolved_config = config or load_config()
    resolved_model = resolve_review_model(
        normalized,
        model=model,
        config=resolved_config,
    )

    if normalized == "openai":
        try:
            from .openai_consistency_reviewer import OpenAIConsistencyReviewer
        except ModuleNotFoundError as exc:
            if exc.name != "openai":
                raise
            raise TranslationProviderConfigurationError(
                "OpenAI support is not installed. Install subtitle-translator[openai]."
            ) from exc

        return OpenAIConsistencyReviewer(client=client, model=resolved_model)

    if not resolved_config.gemini_api_key and client is None:
        raise TranslationProviderConfigurationError(
            "Gemini API key is not configured. Set GEMINI_API_KEY."
        )

    try:
        from .gemini_consistency_reviewer import GeminiConsistencyReviewer
    except ModuleNotFoundError as exc:
        if exc.name not in {"google", "google.genai"}:
            raise
        raise TranslationProviderConfigurationError(
            "Gemini support is not installed. Install subtitle-translator[gemini]."
        ) from exc

    return GeminiConsistencyReviewer(
        client=client,
        model=resolved_model,
        api_key=resolved_config.gemini_api_key,
    )
