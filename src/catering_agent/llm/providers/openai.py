"""OpenAI adapter for one strict JSON-schema event-brief response."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from openai import OpenAI

from catering_agent.constants import LLM_REQUEST_TIMEOUT_S, LLM_TEMPERATURE_EXTRACTION
from catering_agent.llm.providers.base import LLMProviderError


class OpenAIBriefExtractionProvider:
    """Use strict Structured Outputs and return only the parsed JSON object."""

    provider_name = "openai"

    def __init__(
        self, api_key: str, model_id: str, *, client: Any | None = None
    ) -> None:
        self.model_id = model_id
        self._client: Any = client or OpenAI(
            api_key=api_key, timeout=LLM_REQUEST_TIMEOUT_S
        )

    def extract(
        self,
        *,
        system_prompt: str,
        user_brief: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._client.responses.create(
            model=self.model_id,
            temperature=LLM_TEMPERATURE_EXTRACTION,
            store=False,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_brief},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "event_brief",
                    "strict": True,
                    "schema": dict(output_schema),
                }
            },
        )
        return _structured_output(response, "event-brief")

    def select_menu(
        self,
        *,
        system_prompt: str,
        selection_input: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._client.responses.create(
            model=self.model_id,
            temperature=LLM_TEMPERATURE_EXTRACTION,
            store=False,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": selection_input},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "menu_selection",
                    "strict": True,
                    "schema": dict(output_schema),
                }
            },
        )
        return _structured_output(response, "menu-selection")


def _structured_output(response: Any, request_name: str) -> Mapping[str, object]:
    try:
        parsed = json.loads(response.output_text)
    except (AttributeError, TypeError, json.JSONDecodeError) as error:
        raise LLMProviderError(
            f"OpenAI did not return a complete structured {request_name}"
        ) from error
    if not isinstance(parsed, Mapping):
        raise LLMProviderError(f"OpenAI {request_name} output must be an object")
    return parsed
