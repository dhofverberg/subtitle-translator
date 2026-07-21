"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Config:
    """Configuration values used by the application."""

    openai_api_key: str | None = None


def load_config() -> Config:
    """Load application configuration from environment variables."""

    return Config(openai_api_key=os.environ.get("OPENAI_API_KEY"))
