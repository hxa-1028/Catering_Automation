"""Fail-closed validation for a structured event brief."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from catering_agent.domain.models import EventBrief, NeedInput


class IntakeAssessment(BaseModel):
    """The next safe intake action for one unmodified event brief."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "NEEDS_CLARIFICATION"]
    brief: EventBrief
    needs_input: tuple[NeedInput, ...] = ()


def assess_event_brief(
    brief: EventBrief,
    *,
    reference_date: date | None = None,
    require_venue_id: bool = True,
) -> IntakeAssessment:
    """Return every missing or invalid required field without supplying a value."""

    needs_input: list[NeedInput] = []
    _require_client_name(brief.client_name, needs_input)
    _require_text(brief.event_location, "event_location", needs_input)
    _require_regional_specification(brief, needs_input)
    if require_venue_id:
        _require_text(brief.venue_id, "venue_id", needs_input)
    _require_guest_count(brief, needs_input)
    _require_text(brief.event_type, "event_type", needs_input)
    _require_service_styles(brief, needs_input)
    _require_text(brief.preferred_language, "preferred_language", needs_input)
    _require_event_date(brief.event_date, reference_date or date.today(), needs_input)

    return IntakeAssessment(
        status="NEEDS_CLARIFICATION" if needs_input else "READY",
        brief=brief,
        needs_input=tuple(needs_input),
    )


def _require_text(value: str | None, field: str, needs_input: list[NeedInput]) -> None:
    if value is None or not value.strip():
        needs_input.append(NeedInput(field=field, reason="missing"))


def _require_client_name(value: str | None, needs_input: list[NeedInput]) -> None:
    if value is None or not value.strip():
        needs_input.append(NeedInput(field="client_name", reason="missing"))
    elif len(value) > 200:
        needs_input.append(NeedInput(field="client_name", reason="too_long"))


def _require_regional_specification(
    brief: EventBrief, needs_input: list[NeedInput]
) -> None:
    if brief.region_spec_id is None and brief.region_spec_version is None:
        needs_input.append(NeedInput(field="regional_specification", reason="missing"))
    elif brief.region_spec_id is None or brief.region_spec_version is None:
        needs_input.append(
            NeedInput(field="regional_specification", reason="incomplete")
        )


def _require_guest_count(brief: EventBrief, needs_input: list[NeedInput]) -> None:
    if brief.guest_count is None:
        needs_input.append(NeedInput(field="guest_count", reason="missing"))


def _require_service_styles(brief: EventBrief, needs_input: list[NeedInput]) -> None:
    if not brief.service_styles:
        needs_input.append(NeedInput(field="service_styles", reason="missing"))


def _require_event_date(
    event_date: date | None, reference_date: date, needs_input: list[NeedInput]
) -> None:
    if event_date is None:
        needs_input.append(NeedInput(field="event_date", reason="missing"))
    elif event_date < reference_date:
        needs_input.append(NeedInput(field="event_date", reason="in_past"))
