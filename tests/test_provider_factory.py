from __future__ import annotations

import sys
import types

import pytest

from subtitle_translator.config import Config
from subtitle_translator.providers.factory import (
    TranslationProviderConfigurationError,
    create_consistency_reviewer,
    create_translation_provider,
    normalize_provider_name,
    normalize_review_provider_name,
    resolve_review_model,
    resolve_translation_model,
)


def test_provider_name_normalization():
    assert normalize_provider_name(" OPENAI ") == "openai"
    assert normalize_review_provider_name(" GeMiNi ") == "gemini"


def test_unknown_review_provider_is_rejected():
    with pytest.raises(TranslationProviderConfigurationError, match="Unknown review provider"):
        normalize_review_provider_name("azure")


def test_model_resolution_order_for_openai_and_gemini():
    config = Config(
        openai_model="openai-normal",
        openai_review_model="openai-review",
        gemini_api_key="gemini-key",
        gemini_model="gemini-normal",
        gemini_review_model="gemini-review",
    )

    assert resolve_review_model("openai", config=config) == "openai-review"
    assert resolve_review_model("gemini", config=config) == "gemini-review"
    assert resolve_review_model("openai", model="cli-model", config=config) == "cli-model"
    assert resolve_translation_model("openai", model="translation-override", config=config) == (
        "translation-override"
    )
    assert resolve_translation_model("gemini", config=config) == "gemini-normal"


def test_review_model_falls_back_to_normal_model_when_review_env_missing():
    config = Config(
        openai_model="openai-normal",
        gemini_api_key="gemini-key",
        gemini_model="gemini-normal",
    )

    assert resolve_review_model("openai", config=config) == "openai-normal"
    assert resolve_review_model("gemini", config=config) == "gemini-normal"


def test_create_consistency_reviewer_for_openai_without_gemini_sdk(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOpenAIReviewer:
        def __init__(self, client=None, model=None):
            captured["client"] = client
            captured["model"] = model

    fake_module = types.ModuleType("subtitle_translator.providers.openai_consistency_reviewer")
    fake_module.OpenAIConsistencyReviewer = FakeOpenAIReviewer
    monkeypatch.setitem(
        sys.modules,
        "subtitle_translator.providers.openai_consistency_reviewer",
        fake_module,
    )

    reviewer = create_consistency_reviewer(
        "openai",
        config=Config(openai_model="openai-normal", openai_review_model="openai-review"),
        client=object(),
    )

    assert isinstance(reviewer, FakeOpenAIReviewer)
    assert captured["model"] == "openai-review"


def test_create_consistency_reviewer_for_gemini_without_openai_sdk(monkeypatch):
    captured: dict[str, object] = {}

    class FakeGeminiReviewer:
        def __init__(self, client=None, model=None, api_key=None):
            captured["client"] = client
            captured["model"] = model
            captured["api_key"] = api_key

    fake_module = types.ModuleType("subtitle_translator.providers.gemini_consistency_reviewer")
    fake_module.GeminiConsistencyReviewer = FakeGeminiReviewer
    monkeypatch.setitem(
        sys.modules,
        "subtitle_translator.providers.gemini_consistency_reviewer",
        fake_module,
    )

    reviewer = create_consistency_reviewer(
        "gemini",
        config=Config(gemini_api_key="gemini-key", gemini_model="gemini-normal"),
        client=object(),
    )

    assert isinstance(reviewer, FakeGeminiReviewer)
    assert captured["model"] == "gemini-normal"
    assert captured["api_key"] == "gemini-key"


def test_create_consistency_reviewer_rejects_missing_gemini_key_without_client():
    with pytest.raises(
        TranslationProviderConfigurationError,
        match="Gemini API key is not configured",
    ):
        create_consistency_reviewer(
            "gemini",
            config=Config(gemini_api_key=None),
        )


def test_create_translation_provider_uses_selected_provider_model_only(monkeypatch):
    class FakeOpenAIProvider:
        def __init__(self, client=None, model=None):
            self.model = model

    class FakeGeminiProvider:
        def __init__(self, client=None, model=None, api_key=None):
            self.model = model
            self.api_key = api_key

    openai_module = types.ModuleType("subtitle_translator.providers.openai_provider")
    openai_module.OpenAIProvider = FakeOpenAIProvider
    gemini_module = types.ModuleType("subtitle_translator.providers.gemini_provider")
    gemini_module.GeminiProvider = FakeGeminiProvider
    monkeypatch.setitem(
        sys.modules,
        "subtitle_translator.providers.openai_provider",
        openai_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "subtitle_translator.providers.gemini_provider",
        gemini_module,
    )

    config = Config(
        openai_model="openai-normal",
        gemini_api_key="gemini-key",
        gemini_model="gemini-normal",
    )

    openai_provider = create_translation_provider("openai", config=config)
    gemini_provider = create_translation_provider("gemini", config=config)

    assert openai_provider.model == "openai-normal"
    assert gemini_provider.model == "gemini-normal"
    assert gemini_provider.api_key == "gemini-key"
