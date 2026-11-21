from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from catering_agent.catalog.ingestion import parse_catalog_manifest
from catering_agent.catalog.resolution import (
    CatalogLookup,
    CatalogResolution,
    CatalogSnapshot,
    resolve_catalog,
)
from catering_agent.integrations.local_source import SourceDocument
from catering_agent.rules.pricing import PricingError, price_menu

ROOT = Path(__file__).parents[3]
SAMPLE_PATH = ROOT / "data" / "samples" / "catalog.json"
EVENT_DATE = date(2026, 6, 1)


def test_prices_selected_menu_with_dynamic_guest_count_and_venue_fee() -> None:
    snapshot, resolution = _resolved_snapshot()
    assert resolution.venue is not None
    assert resolution.regional_specification is not None
    lunch = next(
        menu for menu in resolution.eligible_menus if menu.menu_id == "sample-lunch"
    )

    result = price_menu(
        menu=lunch,
        venue=resolution.venue,
        regional_specification=resolution.regional_specification,
        event_date=EVENT_DATE,
        guest_count=50,
        price_list_items=snapshot.price_list_items,
    )

    line_amounts = [
        (line.line_item_id, line.quantity, line.total.amount)
        for line in result.line_items
    ]
    assert line_amounts == [
        ("sample-lunch-service", Decimal("50"), Decimal("1500.00")),
        ("sample-venue-fee", Decimal("1"), Decimal("100.00")),
    ]
    assert result.total.amount == Decimal("1600.00")
    assert len(result.cited_source_refs) == 2


def test_menu_without_an_explicit_price_mapping_fails_closed() -> None:
    snapshot, resolution = _resolved_snapshot()
    assert resolution.venue is not None
    assert resolution.regional_specification is not None
    station = next(menu for menu in snapshot.menus if menu.menu_id == "sample-station")
    studio = next(
        venue for venue in snapshot.venues if venue.venue_id == "sample-studio-loft"
    )

    with pytest.raises(PricingError, match="missing_menu_price"):
        price_menu(
            menu=station,
            venue=studio,
            regional_specification=resolution.regional_specification,
            event_date=EVENT_DATE,
            guest_count=50,
            price_list_items=snapshot.price_list_items,
        )


def test_unsupported_unit_never_receives_an_invented_quantity() -> None:
    snapshot, resolution = _resolved_snapshot()
    assert resolution.venue is not None
    assert resolution.regional_specification is not None
    lunch = next(
        menu for menu in resolution.eligible_menus if menu.menu_id == "sample-lunch"
    )
    prices = tuple(
        price.model_copy(update={"unit": "per_hour"})
        if price.sku == "sample-lunch-service"
        else price
        for price in snapshot.price_list_items
    )

    with pytest.raises(PricingError, match="unsupported_price_unit"):
        price_menu(
            menu=lunch,
            venue=resolution.venue,
            regional_specification=resolution.regional_specification,
            event_date=EVENT_DATE,
            guest_count=50,
            price_list_items=prices,
        )


def test_minimum_quantity_requires_clarification_instead_of_adjusting_count() -> None:
    snapshot, resolution = _resolved_snapshot()
    assert resolution.venue is not None
    assert resolution.regional_specification is not None
    lunch = next(
        menu for menu in resolution.eligible_menus if menu.menu_id == "sample-lunch"
    )
    prices = tuple(
        price.model_copy(update={"min_qty": Decimal("51")})
        if price.sku == "sample-lunch-service"
        else price
        for price in snapshot.price_list_items
    )

    with pytest.raises(PricingError, match="minimum_quantity_not_met"):
        price_menu(
            menu=lunch,
            venue=resolution.venue,
            regional_specification=resolution.regional_specification,
            event_date=EVENT_DATE,
            guest_count=50,
            price_list_items=prices,
        )


def _resolved_snapshot() -> tuple[CatalogSnapshot, CatalogResolution]:
    content = SAMPLE_PATH.read_bytes()
    snapshot = CatalogSnapshot.from_bundle(
        parse_catalog_manifest(
            SourceDocument(
                provider="local_filesystem",
                provider_source_id="catalog.json",
                content_hash=sha256(content).hexdigest(),
                content=content,
            )
        )
    )
    resolution = resolve_catalog(
        snapshot,
        CatalogLookup.model_validate(
            {
                "region_spec_id": "sample-us-west",
                "region_spec_version": "1",
                "venue_query": "Sample Harbor Hall",
                "event_date": EVENT_DATE,
                "event_type": "corporate",
                "service_styles": ("buffet",),
                "language": "en-US",
            }
        ),
    )
    assert resolution.status == "RESOLVED"
    return snapshot, resolution
