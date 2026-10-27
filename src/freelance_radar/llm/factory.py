"""Build LLM client from settings."""

from __future__ import annotations

from freelance_radar.config import Settings
from freelance_radar.llm.base import LLMClient
from freelance_radar.llm.mock import MockLLMClient
from freelance_radar.llm.openai_compatible import OpenAICompatibleClient


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_use_mock or not settings.llm_api_key:
        return MockLLMClient()
    return OpenAICompatibleClient(
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout=float(settings.llm_timeout_seconds),
        max_retries=settings.llm_max_retries,
    )
