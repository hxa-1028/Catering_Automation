"""Anthropic adapter for one forced structured event-brief tool call."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from anthropic import Anthropic

from catering_agent.constants import LLM_REQUEST_TIMEOUT_S, LLM_TEMPERATURE_EXTRACTION
from catering_agent.llm.providers.base import LLMProviderError


class AnthropicBriefExtractionProvider:
    """Use one forced client tool call and return only its validated input."""

    provider_name = "anthropic"

    def __init__(
        self, api_key: str, model_id: str, *, client: Any | None = None
    ) -> None:
        self.model_id = model_id
        self._client: Any = client or Anthropic(
            api_key=api_key, timeout=LLM_REQUEST_TIMEOUT_S
        )

    def extract(
        self,
        *,
        system_prompt: str,
        user_brief: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            temperature=LLM_TEMPERATURE_EXTRACTION,
            system=system_prompt,
            messages=[{"role": "user", "content": user_brief}],
            tools=[
                {
                    "name": "submit_event_brief",
                    "description": "Submit only the structured event brief extraction.",
                    "strict": True,
                    "input_schema": dict(output_schema),
                }
            ],
            tool_choice={
                "type": "tool",
                "name": "submit_event_brief",
                "disable_parallel_tool_use": True,
            },
        )
        for block in response.content:
            tool_input = getattr(block, "input", None)
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "submit_event_brief"
                and isinstance(tool_input, Mapping)
            ):
                return tool_input
        raise LLMProviderError("Anthropic did not return the event-brief tool input")

    def select_menu(
        self,
        *,
        system_prompt: str,
        selection_input: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            temperature=LLM_TEMPERATURE_EXTRACTION,
            system=system_prompt,
            messages=[{"role": "user", "content": selection_input}],
            tools=[
                {
                    "name": "submit_menu_selection",
                    "description": "Submit only one supplied menu ID.",
                    "strict": True,
                    "input_schema": dict(output_schema),
                }
            ],
            tool_choice={
                "type": "tool",
                "name": "submit_menu_selection",
                "disable_parallel_tool_use": True,
            },
        )
        for block in response.content:
            tool_input = getattr(block, "input", None)
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "submit_menu_selection"
                and isinstance(tool_input, Mapping)
            ):
                return tool_input
        raise LLMProviderError("Anthropic did not return the menu-selection tool input")
