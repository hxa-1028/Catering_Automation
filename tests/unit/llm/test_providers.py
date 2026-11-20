from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from catering_agent.config import Settings
from catering_agent.llm.providers.anthropic import AnthropicBriefExtractionProvider
from catering_agent.llm.providers.base import LLMConfigurationError
from catering_agent.llm.providers.factory import create_brief_extraction_provider
from catering_agent.llm.providers.openai import OpenAIBriefExtractionProvider


def test_openai_provider_requests_strict_json_schema() -> None:
    responses = _OpenAIResponses()
    provider = OpenAIBriefExtractionProvider(
        "sanitized-key", "configured-model", client=SimpleNamespace(responses=responses)
    )

    result = provider.extract(
        system_prompt="extract",
        user_brief="brief",
        output_schema={"type": "object", "properties": {}},
    )

    assert result == {"field_evidence": {}}
    assert responses.kwargs["store"] is False
    assert responses.kwargs["text"]["format"]["strict"] is True
    assert responses.kwargs["text"]["format"]["type"] == "json_schema"


def test_openai_provider_requests_strict_menu_selection_schema() -> None:
    responses = _OpenAIResponses()
    provider = OpenAIBriefExtractionProvider(
        "sanitized-key", "configured-model", client=SimpleNamespace(responses=responses)
    )

    provider.select_menu(
        system_prompt="select",
        selection_input="candidates",
        output_schema={"type": "object", "properties": {}},
    )

    assert responses.kwargs["text"]["format"]["name"] == "menu_selection"
    assert responses.kwargs["text"]["format"]["strict"] is True


def test_anthropic_provider_forces_only_the_structured_output_tool() -> None:
    messages = _AnthropicMessages()
    provider = AnthropicBriefExtractionProvider(
        "sanitized-key", "configured-model", client=SimpleNamespace(messages=messages)
    )

    result = provider.extract(
        system_prompt="extract",
        user_brief="brief",
        output_schema={"type": "object", "properties": {}},
    )

    assert result == {"field_evidence": {}}
    assert messages.kwargs["tool_choice"]["type"] == "tool"
    assert messages.kwargs["tool_choice"]["name"] == "submit_event_brief"
    assert messages.kwargs["tools"][0]["strict"] is True
    assert messages.kwargs["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {},
    }


def test_anthropic_provider_forces_only_the_menu_selection_tool() -> None:
    messages = _AnthropicMessages()
    provider = AnthropicBriefExtractionProvider(
        "sanitized-key", "configured-model", client=SimpleNamespace(messages=messages)
    )

    provider.select_menu(
        system_prompt="select",
        selection_input="candidates",
        output_schema={"type": "object", "properties": {}},
    )

    assert messages.kwargs["tool_choice"]["name"] == "submit_menu_selection"
    assert messages.kwargs["tools"][0]["strict"] is True


def test_factory_requires_a_non_blank_model_id(tmp_path: Path) -> None:
    secret_path = tmp_path / "llm_api_key"
    secret_path.write_text("sanitized-test-key", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        llm_api_key_secret_file=secret_path,
        llm_model=" ",
    )

    with pytest.raises(LLMConfigurationError, match="model ID"):
        create_brief_extraction_provider(settings)


class _OpenAIResponses:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps({"field_evidence": {}}))


class _AnthropicMessages:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        tool_name = kwargs["tools"][0]["name"]
        assert isinstance(tool_name, str)
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name=tool_name,
                    input={"field_evidence": {}},
                )
            ]
        )
