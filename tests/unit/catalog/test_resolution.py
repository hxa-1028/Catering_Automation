from __future__ import annotations

from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path

from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import (
    CatalogLookup,
    CatalogSnapshot,
    resolve_catalog,
)
from catering_agent.integrations.local_source import SourceDocument

ROOT = Path(__file__).parents[3]
SAMPLE_PATH = ROOT / "data" / "samples" / "catalog.json"


def test_resolves_an_exact_alias_and_only_eligible_menus() -> None:
    resolution = resolve_catalog(
        _snapshot(),
        _lookup(
            venue_query="  harbor hall  ",
            event_type="corporate",
            service_styles=("buffet",),
        ),
    )

    assert resolution.status == "RESOLVED"
    assert resolution.venue is not None
    assert resolution.venue.venue_id == "sample-harbor-hall"
    assert [menu.menu_id for menu in resolution.eligible_menus] == [
        "sample-breakfast",
        "sample-lunch",
    ]
    assert all(menu.source_ref.source_ref_id for menu in resolution.eligible_menus)


def test_unknown_region_fails_closed_without_catalog_records() -> None:
    resolution = resolve_catalog(_snapshot(), _lookup(region_spec_id="unknown-region"))

    assert resolution.status == "NEEDS_CLARIFICATION"
    assert resolution.regional_specification is None
    assert resolution.venue is None
    assert resolution.eligible_menus == ()
    assert resolution.needs_input[0].model_dump() == {
        "field": "regional_specification",
        "reason": "unknown",
    }


def test_partial_venue_name_is_not_treated_as_a_fuzzy_match() -> None:
    resolution = resolve_catalog(_snapshot(), _lookup(venue_query="Harbor"))

    assert resolution.status == "NEEDS_CLARIFICATION"
    assert resolution.needs_input[0].model_dump() == {
        "field": "venue",
        "reason": "not_in_regional_catalog",
    }


def test_ambiguous_alias_requires_clarification() -> None:
    snapshot = _snapshot()
    duplicate_alias = snapshot.venues[1].model_copy(
        update={"aliases": ("Harbor Hall",)}
    )
    resolution = resolve_catalog(
        replace(
            snapshot, venues=(snapshot.venues[0], duplicate_alias, *snapshot.venues[2:])
        ),
        _lookup(venue_query="Harbor Hall"),
    )

    assert resolution.status == "NEEDS_CLARIFICATION"
    assert resolution.needs_input[0].model_dump() == {
        "field": "venue",
        "reason": "ambiguous",
    }


def test_inactive_date_or_unsupported_language_fails_closed() -> None:
    inactive = resolve_catalog(_snapshot(), _lookup(event_date=date(2025, 12, 31)))
    unsupported_language = resolve_catalog(_snapshot(), _lookup(language="fr-FR"))

    assert inactive.needs_input[0].model_dump() == {
        "field": "regional_specification",
        "reason": "not_effective_on_event_date",
    }
    assert unsupported_language.needs_input[0].model_dump() == {
        "field": "proposal_language",
        "reason": "unsupported",
    }


def test_menu_from_another_region_never_leaks_into_resolution() -> None:
    snapshot = _snapshot()
    other_region_menu = snapshot.menus[0].model_copy(
        update={"region_spec_id": "other-region", "region_spec_version": "1"}
    )
    resolution = resolve_catalog(
        replace(snapshot, menus=(*snapshot.menus, other_region_menu)),
        _lookup(event_type="corporate", service_styles=("buffet",)),
    )

    assert resolution.status == "RESOLVED"
    assert [menu.menu_id for menu in resolution.eligible_menus] == [
        "sample-breakfast",
        "sample-lunch",
    ]


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


def _lookup(**changes: object) -> CatalogLookup:
    payload: dict[str, object] = {
        "region_spec_id": "sample-us-west",
        "region_spec_version": "1",
        "venue_query": "Sample Harbor Hall",
        "event_date": date(2026, 6, 1),
        "event_type": "wedding",
        "service_styles": ("seated",),
        "language": "en-US",
    }
    payload.update(changes)
    return CatalogLookup.model_validate(payload)
