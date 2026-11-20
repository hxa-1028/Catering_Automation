from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import pytest

from catering_agent.intake.extraction import (
    BriefExtractionError,
    ExtractionContext,
    extract_event_brief,
)


@dataclass
class FakeBriefProvider:
    response: Mapping[str, object]
    provider_name: str = "fake"
    model_id: str = "fake-model"
    requests: list[dict[str, object]] = field(default_factory=list)

    def extract(
        self,
        *,
        system_prompt: str,
        user_brief: str,
        output_schema: Mapping[str, object],
    ) -> Mapping[str, object]:
        self.requests.append(
            {
                "system_prompt": system_prompt,
                "user_brief": user_brief,
                "output_schema": output_schema,
            }
        )
        return self.response


def test_evidence_backed_extraction_keeps_context_and_venue_unresolved() -> None:
    brief_text = (
        "Avery Nguyen is planning a corporate buffet for 50 guests at Harbor Hall "
        "on 2026-06-01."
    )
    provider = FakeBriefProvider(
        _response(
            client_name="Avery Nguyen",
            event_date="2026-06-01",
            venue_query="Harbor Hall",
            guest_count=50,
            event_type="corporate",
            service_styles=["buffet"],
            field_evidence=_evidence(
                client_name={"evidence_span": "Avery Nguyen", "confidence": 0.9},
                event_date={"evidence_span": "2026-06-01", "confidence": 0.9},
                venue_query={"evidence_span": "Harbor Hall", "confidence": 0.9},
                guest_count={"evidence_span": "50 guests", "confidence": 0.9},
                event_type={"evidence_span": "corporate", "confidence": 0.9},
                service_styles={"evidence_span": "buffet", "confidence": 0.9},
            ),
        )
    )

    result = extract_event_brief(provider, brief_text, _context())

    assert result.brief.client_name == "Avery Nguyen"
    assert result.brief.event_date == date(2026, 6, 1)
    assert result.brief.guest_count == 50
    assert result.brief.region_spec_id == "sample-us-west"
    assert result.brief.region_spec_version == "1"
    assert result.brief.preferred_language == "en-US"
    assert result.brief.venue_id is None
    assert result.venue_query == "Harbor Hall"
    assert "<event_brief>" in str(provider.requests[0]["user_brief"])


def test_value_without_exact_evidence_is_discarded() -> None:
    result = extract_event_brief(
        FakeBriefProvider(
            _response(
                client_name="Invented Name",
                field_evidence=_evidence(
                    client_name={
                        "evidence_span": "not in the input",
                        "confidence": 1,
                    }
                ),
            )
        ),
        "Corporate catering enquiry.",
        _context(),
    )

    assert result.brief.client_name is None
    assert result.brief.field_evidence == {}


def test_provider_output_with_controlled_field_is_rejected() -> None:
    with pytest.raises(BriefExtractionError, match="invalid event-brief schema"):
        extract_event_brief(
            FakeBriefProvider(_response(region_spec_id="model-selected-region")),
            "Corporate catering enquiry.",
            _context(),
        )


def test_ambiguous_date_and_guest_range_are_discarded() -> None:
    result = extract_event_brief(
        FakeBriefProvider(
            _response(
                event_date="2026-09-01",
                guest_count=150,
                field_evidence=_evidence(
                    event_date={"evidence_span": "September", "confidence": 1},
                    guest_count={
                        "evidence_span": "140-160 guests",
                        "confidence": 1,
                    },
                ),
            )
        ),
        "We expect 140-160 guests in September.",
        _context(),
    )

    assert result.brief.event_date is None
    assert result.brief.guest_count is None
    assert result.brief.field_evidence == {}


def test_provider_schema_uses_fixed_required_strict_objects() -> None:
    provider = FakeBriefProvider(_response(), provider_name="openai")

    extract_event_brief(provider, "Corporate catering enquiry.", _context())

    schema = provider.requests[0]["output_schema"]
    assert isinstance(schema, dict)
    for object_schema in _object_schemas(schema):
        assert object_schema.get("additionalProperties") is False
        assert set(object_schema.get("required", ())) == set(
            object_schema.get("properties", {})
        )


def test_anthropic_schema_omits_unsupported_strict_constraints() -> None:
    provider = FakeBriefProvider(_response(), provider_name="anthropic")

    extract_event_brief(provider, "Corporate catering enquiry.", _context())

    assert '"minimum"' not in json.dumps(provider.requests[0]["output_schema"])
    assert '"maximum"' not in json.dumps(provider.requests[0]["output_schema"])
    assert '"minLength"' not in json.dumps(provider.requests[0]["output_schema"])
    assert '"maxLength"' not in json.dumps(provider.requests[0]["output_schema"])


def _context() -> ExtractionContext:
    return ExtractionContext(
        region_spec_id="sample-us-west",
        region_spec_version="1",
        preferred_language="en-US",
    )


def _response(**changes: object) -> dict[str, object]:
    response: dict[str, object] = {
        "client_name": None,
        "client_contact": None,
        "event_date": None,
        "event_location": None,
        "venue_query": None,
        "guest_count": None,
        "event_type": None,
        "service_styles": None,
        "menu_preferences": None,
        "dietary_requirements": None,
        "other_requirements": None,
        "field_evidence": _evidence(),
    }
    response.update(changes)
    return response


def _evidence(**changes: object) -> dict[str, object]:
    evidence: dict[str, object] = {
        "client_name": None,
        "client_contact": None,
        "event_date": None,
        "event_location": None,
        "venue_query": None,
        "guest_count": None,
        "event_type": None,
        "service_styles": None,
        "menu_preferences": None,
        "dietary_requirements": None,
        "other_requirements": None,
    }
    evidence.update(changes)
    return evidence


def _object_schemas(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        nested = [item for child in value.values() for item in _object_schemas(child)]
        return ([value] if value.get("type") == "object" else []) + nested
    if isinstance(value, list):
        return [item for child in value for item in _object_schemas(child)]
    return []
