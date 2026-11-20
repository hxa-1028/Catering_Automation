from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from pathlib import Path

from catering_agent.agent.pipeline import PipelineRequest, run_pipeline
from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import CatalogSnapshot
from catering_agent.intake.extraction import ExtractionContext
from catering_agent.integrations.local_source import SourceDocument

ROOT = Path(__file__).parents[3]
SAMPLE_PATH = ROOT / "data" / "samples" / "catalog.json"
BRIEF_TEXT = (
    "Synthetic Client is planning a corporate buffet for 50 guests at Sample "
    "Harbor Hall in Sample City on 2026-06-01."
)


@dataclass
class FakeBriefProvider:
    response: Mapping[str, object]
    provider_name: str = "fake"
    model_id: str = "fake-model"
    requests: list[dict[str, object]] = field(default_factory=list)

    def extract(self, **kwargs: object) -> Mapping[str, object]:
        self.requests.append(kwargs)
        return self.response


def test_resolves_catalog_after_one_evidence_backed_extraction() -> None:
    provider = FakeBriefProvider(_complete_response())

    result = run_pipeline(provider, _snapshot(), _request())

    assert result.status == "SOURCES_RESOLVED"
    assert result.brief.venue_id == "sample-harbor-hall"
    assert result.catalog_resolution is not None
    assert [menu.menu_id for menu in result.catalog_resolution.eligible_menus] == [
        "sample-breakfast",
        "sample-lunch",
    ]
    assert len(provider.requests) == 1


def test_missing_intake_value_stops_before_catalog_resolution() -> None:
    response = _complete_response()
    response["client_name"] = None
    response["field_evidence"] = _evidence()

    result = run_pipeline(FakeBriefProvider(response), _snapshot(), _request())

    assert result.status == "NEEDS_CLARIFICATION"
    assert result.catalog_resolution is None
    assert [item.model_dump() for item in result.needs_input] == [
        {"field": "client_name", "reason": "missing"}
    ]


def test_missing_venue_phrase_stops_before_catalog_resolution() -> None:
    response = _complete_response()
    response["venue_query"] = None
    response["field_evidence"] = _evidence(venue_query=None)

    result = run_pipeline(FakeBriefProvider(response), _snapshot(), _request())

    assert result.status == "NEEDS_CLARIFICATION"
    assert result.catalog_resolution is None
    assert [item.model_dump() for item in result.needs_input] == [
        {"field": "venue", "reason": "missing"}
    ]


def test_catalog_clarification_is_returned_without_a_guess() -> None:
    response = _complete_response()
    response["venue_query"] = "Unknown Hall"
    response["field_evidence"] = _evidence(
        venue_query={"evidence_span": "Unknown Hall", "confidence": 0.9}
    )

    result = run_pipeline(
        FakeBriefProvider(response),
        _snapshot(),
        _request(brief_text=BRIEF_TEXT.replace("Sample Harbor", "Unknown")),
    )

    assert result.status == "NEEDS_CLARIFICATION"
    assert result.catalog_resolution is not None
    assert [item.model_dump() for item in result.needs_input] == [
        {"field": "venue", "reason": "not_in_regional_catalog"}
    ]


def test_invalid_extraction_falls_back_to_clarification() -> None:
    result = run_pipeline(FakeBriefProvider({}), _snapshot(), _request())

    assert result.status == "NEEDS_CLARIFICATION"
    assert result.extraction is None
    assert [item.model_dump() for item in result.needs_input] == [
        {"field": "event_brief", "reason": "extraction_failed"}
    ]


def _request(**changes: object) -> PipelineRequest:
    payload: dict[str, object] = {
        "brief_text": BRIEF_TEXT,
        "context": ExtractionContext(
            region_spec_id="sample-us-west",
            region_spec_version="1",
            preferred_language="en-US",
        ),
        "reference_date": date(2026, 1, 1),
    }
    payload.update(changes)
    return PipelineRequest.model_validate(payload)


def _snapshot() -> CatalogSnapshot:
    content = SAMPLE_PATH.read_bytes()
    bundle = parse_catalog_manifest(
        SourceDocument(
            provider="local_filesystem",
            provider_source_id="catalog.json",
            content_hash=sha256(content).hexdigest(),
            content=content,
        )
    )
    return CatalogSnapshot.from_bundle(bundle)


def _complete_response() -> dict[str, object]:
    return {
        "client_name": "Synthetic Client",
        "client_contact": None,
        "event_date": "2026-06-01",
        "event_location": "Sample City",
        "venue_query": "Sample Harbor Hall",
        "guest_count": 50,
        "event_type": "corporate",
        "service_styles": ["buffet"],
        "menu_preferences": None,
        "dietary_requirements": None,
        "other_requirements": None,
        "field_evidence": _evidence(),
    }


def _evidence(**changes: object) -> dict[str, object]:
    evidence: dict[str, object] = {
        "client_name": {"evidence_span": "Synthetic Client", "confidence": 0.9},
        "client_contact": None,
        "event_date": {"evidence_span": "2026-06-01", "confidence": 0.9},
        "event_location": {"evidence_span": "Sample City", "confidence": 0.9},
        "venue_query": {"evidence_span": "Sample Harbor Hall", "confidence": 0.9},
        "guest_count": {"evidence_span": "50 guests", "confidence": 0.9},
        "event_type": {"evidence_span": "corporate", "confidence": 0.9},
        "service_styles": {"evidence_span": "buffet", "confidence": 0.9},
        "menu_preferences": None,
        "dietary_requirements": None,
        "other_requirements": None,
    }
    evidence.update(changes)
    return evidence
