"""Schema-constrained LLM extraction that preserves deterministic control fields."""

from __future__ import annotations

import re
from datetime import date
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catering_agent.domain.models import EventBrief, FieldEvidence, Identifier
from catering_agent.llm.providers.base import BriefExtractionProvider

PROMPT_VERSION: Literal["extract_brief.v1"] = "extract_brief.v1"
_EXTRACTED_FIELDS = frozenset(
    {
        "client_name",
        "client_contact",
        "event_date",
        "event_location",
        "venue_query",
        "guest_count",
        "event_type",
        "service_styles",
        "menu_preferences",
        "dietary_requirements",
        "other_requirements",
    }
)


class BriefExtractionError(ValueError):
    """Raised when a provider response cannot be safely accepted as extraction data."""


class ExtractionContext(BaseModel):
    """Fields selected by approved configuration, never inferred by the LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_spec_id: Identifier
    region_spec_version: Identifier
    preferred_language: Identifier


class EventBriefEvidence(BaseModel):
    """Fixed evidence keys keep strict provider schemas compatible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_name: FieldEvidence | None
    client_contact: FieldEvidence | None
    event_date: FieldEvidence | None
    event_location: FieldEvidence | None
    venue_query: FieldEvidence | None
    guest_count: FieldEvidence | None
    event_type: FieldEvidence | None
    service_styles: FieldEvidence | None
    menu_preferences: FieldEvidence | None
    dietary_requirements: FieldEvidence | None
    other_requirements: FieldEvidence | None


class EventBriefExtraction(BaseModel):
    """Only fields a model may extract from the salesperson's own brief text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_name: str | None
    client_contact: str | None
    event_date: date | None
    event_location: str | None
    venue_query: str | None
    guest_count: int | None = Field(ge=1)
    event_type: Identifier | None
    service_styles: tuple[Identifier, ...] | None
    menu_preferences: str | None
    dietary_requirements: str | None
    other_requirements: str | None
    field_evidence: EventBriefEvidence


class BriefExtractionResult(BaseModel):
    """Validated extracted data plus the configured context and model provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    brief: EventBrief
    venue_query: str | None = None
    provider: Identifier
    model: Identifier
    prompt_version: Literal["extract_brief.v1"] = PROMPT_VERSION


def extract_event_brief(
    provider: BriefExtractionProvider,
    brief_text: str,
    context: ExtractionContext,
) -> BriefExtractionResult:
    """Extract evidence-backed user facts while keeping region and language fixed."""

    if not brief_text.strip():
        raise BriefExtractionError("event brief text must not be blank")

    try:
        extraction = EventBriefExtraction.model_validate(
            provider.extract(
                system_prompt=_extract_brief_prompt(),
                user_brief=_delimit_brief(brief_text),
                output_schema=_provider_output_schema(provider.provider_name),
            )
        )
    except ValidationError as error:
        raise BriefExtractionError(
            "provider returned an invalid event-brief schema"
        ) from error

    extracted_values, evidence = _evidence_backed_values(extraction, brief_text)
    venue_query = extracted_values.pop("venue_query", None)
    brief = EventBrief.model_validate(
        {
            **extracted_values,
            "region_spec_id": context.region_spec_id,
            "region_spec_version": context.region_spec_version,
            "preferred_language": context.preferred_language,
            "field_evidence": evidence,
        }
    )
    return BriefExtractionResult(
        brief=brief,
        venue_query=venue_query if isinstance(venue_query, str) else None,
        provider=provider.provider_name,
        model=provider.model_id,
    )


def _evidence_backed_values(
    extraction: EventBriefExtraction, brief_text: str
) -> tuple[dict[str, object], dict[str, FieldEvidence]]:
    values: dict[str, object] = {}
    evidence: dict[str, FieldEvidence] = {}
    for field in _EXTRACTED_FIELDS:
        value = getattr(extraction, field)
        field_evidence = getattr(extraction.field_evidence, field)
        if value is not None and _has_valid_evidence(
            field, value, field_evidence, brief_text
        ):
            assert field_evidence is not None
            values[field] = value
            evidence[field] = field_evidence
    return values, evidence


def _has_valid_evidence(
    field: str, value: object, evidence: FieldEvidence | None, brief_text: str
) -> bool:
    if (
        evidence is None
        or evidence.evidence_span is None
        or evidence.evidence_span not in brief_text
        or evidence.confidence is None
    ):
        return False
    if field == "guest_count":
        return _is_single_explicit_guest_count(value, evidence.evidence_span)
    if field == "event_date":
        return _is_single_explicit_iso_date(value, evidence.evidence_span)
    return True


def _is_single_explicit_guest_count(value: object, evidence_span: str) -> bool:
    # shortcut: written numbers need approved regional parsing rules.
    numbers = re.findall(r"(?<!\d)\d+(?!\d)", evidence_span)
    return isinstance(value, int) and numbers == [str(value)]


def _is_single_explicit_iso_date(value: object, evidence_span: str) -> bool:
    # shortcut: locale-specific date parsing waits for approved regional parsing rules.
    return isinstance(value, date) and re.findall(
        r"\b\d{4}-\d{2}-\d{2}\b", evidence_span
    ) == [value.isoformat()]


def _provider_output_schema(provider_name: str) -> dict[str, object]:
    """Return a strict schema that the selected provider accepts."""

    schema = EventBriefExtraction.model_json_schema()
    if provider_name != "anthropic":
        return schema
    stripped_schema = _without_anthropic_unsupported_constraints(schema)
    assert isinstance(stripped_schema, dict)
    return stripped_schema


def _without_anthropic_unsupported_constraints(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_anthropic_unsupported_constraints(item)
            for key, item in value.items()
            if key not in {"minimum", "maximum", "minLength", "maxLength"}
        }
    if isinstance(value, list):
        return [_without_anthropic_unsupported_constraints(item) for item in value]
    return value


def _extract_brief_prompt() -> str:
    return (
        files("catering_agent.llm.prompts")
        .joinpath("extract_brief.v1.md")
        .read_text(encoding="utf-8")
    )


def _delimit_brief(brief_text: str) -> str:
    return f"<event_brief>\n{brief_text}\n</event_brief>"
