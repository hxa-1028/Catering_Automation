"""Constrained menu selection and exact catalog-source citations."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from catering_agent.catalog.resolution import CatalogResolution
from catering_agent.domain.models import EventBrief, Identifier, Menu, SourceRef
from catering_agent.llm.providers.base import BriefExtractionProvider

PROMPT_VERSION: Literal["select_menu.v1"] = "select_menu.v1"


class MenuSelectionError(ValueError):
    """Raised when a menu-selection response cannot be safely used."""


class InvalidMenuSelectionError(MenuSelectionError):
    """Raised when a response names an ID outside the eligible candidate list."""


class MenuSelectionOutput(BaseModel):
    """The only value an LLM may return for the menu-selection step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_menu_id: Identifier


class MenuSelectionResult(BaseModel):
    """An approved selected menu and exact catalog citations for later stages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_menu: Menu
    cited_source_refs: tuple[SourceRef, ...]
    prompt_version: Literal["select_menu.v1"] = PROMPT_VERSION


def select_menu(
    provider: BriefExtractionProvider,
    brief: EventBrief,
    catalog_resolution: CatalogResolution,
) -> MenuSelectionResult:
    """Select one supplied menu ID and preserve exact source references."""

    if not brief.menu_preferences or not brief.menu_preferences.strip():
        raise MenuSelectionError("menu preferences are required for menu selection")
    if (
        catalog_resolution.venue is None
        or catalog_resolution.regional_specification is None
        or not catalog_resolution.eligible_menus
    ):
        raise MenuSelectionError("resolved catalog records are required")

    candidates = tuple(catalog_resolution.eligible_menus)
    try:
        output = MenuSelectionOutput.model_validate(
            provider.select_menu(
                system_prompt=_selection_prompt(),
                selection_input=_selection_input(brief, candidates),
                output_schema=MenuSelectionOutput.model_json_schema(),
            )
        )
    except ValidationError as error:
        raise MenuSelectionError(
            "provider returned an invalid menu-selection schema"
        ) from error

    selected = next(
        (menu for menu in candidates if menu.menu_id == output.selected_menu_id), None
    )
    if selected is None:
        raise InvalidMenuSelectionError("provider selected an ineligible menu")
    return MenuSelectionResult(
        selected_menu=selected,
        cited_source_refs=(
            catalog_resolution.regional_specification.source_ref,
            catalog_resolution.venue.source_ref,
            selected.source_ref,
        ),
    )


def _selection_prompt() -> str:
    return (
        files("catering_agent.llm.prompts")
        .joinpath("select_menu.v1.md")
        .read_text(encoding="utf-8")
    )


def _selection_input(brief: EventBrief, candidates: tuple[Menu, ...]) -> str:
    language = brief.preferred_language
    assert language is not None
    candidate_payload = [
        {
            "menu_id": menu.menu_id,
            "localized_content": menu.localized_content[language],
        }
        for menu in candidates
    ]
    return (
        "<menu_preferences>\n"
        f"{brief.menu_preferences}\n"
        "</menu_preferences>\n"
        "<eligible_menu_candidates>\n"
        f"{json.dumps(candidate_payload, ensure_ascii=False, sort_keys=True)}\n"
        "</eligible_menu_candidates>"
    )
