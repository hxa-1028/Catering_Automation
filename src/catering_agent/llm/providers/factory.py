"""Create the configured LLM provider without exposing secret values."""

from __future__ import annotations

from catering_agent.config import Settings
from catering_agent.llm.providers.anthropic import AnthropicBriefExtractionProvider
from catering_agent.llm.providers.base import (
    BriefExtractionProvider,
    LLMConfigurationError,
)
from catering_agent.llm.providers.openai import OpenAIBriefExtractionProvider


def create_brief_extraction_provider(settings: Settings) -> BriefExtractionProvider:
    """Create the selected provider only when its model and key are configured."""

    api_key = settings.resolved_llm_api_key()
    if api_key is None:
        raise LLMConfigurationError("LLM API key secret is unavailable")
    model_id = settings.llm_model.strip() if settings.llm_model is not None else ""
    if not model_id:
        raise LLMConfigurationError("LLM model ID is not configured")

    if settings.llm_provider == "anthropic":
        return AnthropicBriefExtractionProvider(api_key, model_id)
    return OpenAIBriefExtractionProvider(api_key, model_id)
