"""Provider-neutral translation interfaces and lazy provider exports."""

from .base import (
    BatchTranslationRequest,
    TranslationProvider,
    TranslationProviderError,
    TranslationRequest,
)

__all__ = [
    "BatchTranslationRequest",
    "OpenAIConsistencyReviewer",
    "OpenAIConsistencyReviewerError",
    "OpenAIProvider",
    "OpenAIProviderError",
    "TranslationProvider",
    "TranslationProviderError",
    "TranslationRequest",
]


def __getattr__(name: str) -> object:
    """Load optional provider SDK integrations only when explicitly requested."""

    if name in {"OpenAIProvider", "OpenAIProviderError"}:
        from .openai_provider import OpenAIProvider, OpenAIProviderError

        return {
            "OpenAIProvider": OpenAIProvider,
            "OpenAIProviderError": OpenAIProviderError,
        }[name]
    if name in {"OpenAIConsistencyReviewer", "OpenAIConsistencyReviewerError"}:
        from .openai_consistency_reviewer import (
            OpenAIConsistencyReviewer,
            OpenAIConsistencyReviewerError,
        )

        return {
            "OpenAIConsistencyReviewer": OpenAIConsistencyReviewer,
            "OpenAIConsistencyReviewerError": OpenAIConsistencyReviewerError,
        }[name]
    if name in {"GeminiProvider", "GeminiProviderError"}:
        from .gemini_provider import GeminiProvider, GeminiProviderError

        return {
            "GeminiProvider": GeminiProvider,
            "GeminiProviderError": GeminiProviderError,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
