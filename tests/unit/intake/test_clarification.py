from __future__ import annotations

from datetime import date

from catering_agent.domain.models import EventBrief
from catering_agent.intake.clarification import assess_event_brief


def test_complete_brief_is_ready_without_mutation() -> None:
    brief = _brief()

    assessment = assess_event_brief(brief, reference_date=date(2026, 6, 1))

    assert assessment.status == "READY"
    assert assessment.brief is brief
    assert assessment.needs_input == ()


def test_missing_required_fields_are_all_returned_for_clarification() -> None:
    assessment = assess_event_brief(
        _brief(
            client_name=" ",
            event_date=None,
            event_location=" ",
            region_spec_id=None,
            region_spec_version=None,
            venue_id=None,
            guest_count=None,
            event_type=None,
            service_styles=(),
            preferred_language=None,
        ),
        reference_date=date(2026, 6, 1),
    )

    assert assessment.status == "NEEDS_CLARIFICATION"
    assert [(item.field, item.reason) for item in assessment.needs_input] == [
        ("client_name", "missing"),
        ("event_location", "missing"),
        ("regional_specification", "missing"),
        ("venue_id", "missing"),
        ("guest_count", "missing"),
        ("event_type", "missing"),
        ("service_styles", "missing"),
        ("preferred_language", "missing"),
        ("event_date", "missing"),
    ]


def test_partial_regional_specification_requires_clarification() -> None:
    assessment = assess_event_brief(
        _brief(region_spec_version=None), reference_date=date(2026, 6, 1)
    )

    assert assessment.status == "NEEDS_CLARIFICATION"
    assert [(item.field, item.reason) for item in assessment.needs_input] == [
        ("regional_specification", "incomplete")
    ]


def test_catalog_pipeline_can_defer_the_venue_id_check() -> None:
    assessment = assess_event_brief(
        _brief(venue_id=None),
        reference_date=date(2026, 6, 1),
        require_venue_id=False,
    )

    assert assessment.status == "READY"


def test_client_name_cannot_exceed_the_supported_length() -> None:
    assessment = assess_event_brief(
        _brief(client_name="x" * 201), reference_date=date(2026, 6, 1)
    )

    assert [(item.field, item.reason) for item in assessment.needs_input] == [
        ("client_name", "too_long")
    ]


def test_event_date_must_not_precede_reference_date() -> None:
    reference_date = date(2026, 6, 1)

    same_day = assess_event_brief(
        _brief(event_date=reference_date), reference_date=reference_date
    )
    past = assess_event_brief(
        _brief(event_date=date(2026, 5, 31)), reference_date=reference_date
    )

    assert same_day.status == "READY"
    assert [(item.field, item.reason) for item in past.needs_input] == [
        ("event_date", "in_past")
    ]


def _brief(**changes: object) -> EventBrief:
    payload: dict[str, object] = {
        "client_name": "Synthetic Client",
        "event_date": date(2026, 6, 1),
        "event_location": "Sample City",
        "region_spec_id": "sample-us-west",
        "region_spec_version": "1",
        "venue_id": "sample-harbor-hall",
        "guest_count": 50,
        "event_type": "corporate",
        "service_styles": ("buffet",),
        "preferred_language": "en-US",
    }
    payload.update(changes)
    return EventBrief.model_validate(payload)
