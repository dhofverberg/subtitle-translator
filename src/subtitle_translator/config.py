"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True, slots=True)
class Config:
    """Configuration values used by the application."""

    openai_api_key: str | None = None
    openai_model: str = DEFAULT_OPENAI_MODEL
    gemini_api_key: str | None = None
    gemini_model: str = DEFAULT_GEMINI_MODEL


def load_config() -> Config:
    """Load application configuration from environment variables."""

    return Config(
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        gemini_model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    )
