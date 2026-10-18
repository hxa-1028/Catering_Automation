from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from catering_agent.domain.models import (
    EffectiveWindow,
    Money,
    ProposalLineItem,
    SourceLocation,
    SourceRef,
)


def source_ref() -> SourceRef:
    return SourceRef(
        source_ref_id="source-ref",
        provider="local",
        provider_source_id="approved-file",
        content_hash="a" * 64,
        location=SourceLocation(sheet="Prices", cell_range="A1"),
        catalog_version="catalog-version",
        region_spec_id="region-spec",
        region_spec_version="version",
    )


def test_source_location_requires_precise_locator() -> None:
    with pytest.raises(ValidationError, match="source location"):
        SourceLocation()


def test_money_rejects_binary_float() -> None:
    with pytest.raises(ValidationError, match="never float"):
        Money(amount=1.5, currency="USD")


def test_effective_window_rejects_reverse_dates() -> None:
    with pytest.raises(ValidationError, match="effective_to"):
        EffectiveWindow(
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 1, 1),
        )


def test_line_item_requires_same_currency_and_source_reference() -> None:
    with pytest.raises(ValidationError, match="currencies must match"):
        ProposalLineItem(
            line_item_id="line-item",
            quantity=Decimal("1"),
            unit="per_guest",
            unit_price=Money(amount=Decimal("1"), currency="USD"),
            total=Money(amount=Decimal("1"), currency="EUR"),
            source_ref=source_ref(),
        )
