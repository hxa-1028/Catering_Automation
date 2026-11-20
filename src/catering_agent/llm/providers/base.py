"""Provider contract for bounded, schema-constrained LLM calls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class LLMConfigurationError(ValueError):
    """Raised when a configured provider cannot be initialized safely."""


class LLMProviderError(RuntimeError):
    """Raised when a provider does not return the required structured output."""


class BriefExtractionProvider(Protocol):
    """A provider that extracts a brief and selects only supplied menu IDs."""

    provider_name: str
    model_id: str

    def extract(
        self,
        *,
        system_prompt: str,
        user_brief: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Extract one structured event brief without invoking application tools."""

    def select_menu(
        self,
        *,
        system_prompt: str,
        selection_input: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        """Select one menu ID from application-supplied candidates only."""
