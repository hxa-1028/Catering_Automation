"""Minimal deterministic pricing for approved menu and venue price records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from catering_agent.domain.models import (
    Menu,
    Money,
    PriceListItem,
    ProposalLineItem,
    RegionalSpecification,
    SourceRef,
    Venue,
)


class PricingError(ValueError):
    """A pricing input is absent or cannot safely be applied."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PricingResult(BaseModel):
    """Computed line items and their complete approved-source provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line_items: tuple[ProposalLineItem, ...]
    total: Money
    cited_source_refs: tuple[SourceRef, ...]


def price_menu(
    *,
    menu: Menu,
    venue: Venue,
    regional_specification: RegionalSpecification,
    event_date: date,
    guest_count: int,
    price_list_items: tuple[PriceListItem, ...],
) -> PricingResult:
    """Price one selected menu and its required venue fees without inference."""

    if menu.price_sku is None:
        raise PricingError("missing_menu_price")
    if guest_count < 1:
        raise PricingError("invalid_guest_count")

    price_skus = (menu.price_sku, *venue.required_fee_skus)
    if len(set(price_skus)) != len(price_skus):
        raise PricingError("duplicate_price_sku")

    line_items = tuple(
        _line_item(
            sku=sku,
            regional_specification=regional_specification,
            event_date=event_date,
            guest_count=guest_count,
            price_list_items=price_list_items,
        )
        for sku in price_skus
    )
    currencies = {line.total.currency for line in line_items}
    if len(currencies) != 1:
        raise PricingError("mixed_currency")
    total = Money(
        amount=sum((line.total.amount for line in line_items), Decimal("0")),
        currency=line_items[0].total.currency,
    )
    return PricingResult(
        line_items=line_items,
        total=total,
        cited_source_refs=tuple(line.source_ref for line in line_items),
    )


def _line_item(
    *,
    sku: str,
    regional_specification: RegionalSpecification,
    event_date: date,
    guest_count: int,
    price_list_items: tuple[PriceListItem, ...],
) -> ProposalLineItem:
    matches = tuple(
        price
        for price in price_list_items
        if (
            price.sku == sku
            and price.region_spec_id == regional_specification.region_spec_id
            and price.region_spec_version == regional_specification.version
            and _is_effective(price, event_date)
        )
    )
    if not matches:
        raise PricingError("price_not_available")
    if len(matches) != 1:
        raise PricingError("ambiguous_price")

    price = matches[0]
    if price.unit_price.currency != regional_specification.currency:
        raise PricingError("price_currency_mismatch")
    if price.unit == "per_guest":
        quantity = Decimal(guest_count)
    elif price.unit == "flat":
        quantity = Decimal("1")
    else:
        raise PricingError("unsupported_price_unit")
    if price.min_qty is not None and quantity < price.min_qty:
        raise PricingError("minimum_quantity_not_met")

    return ProposalLineItem(
        line_item_id=price.sku,
        quantity=quantity,
        unit=price.unit,
        unit_price=price.unit_price,
        total=Money(
            amount=price.unit_price.amount * quantity,
            currency=price.unit_price.currency,
        ),
        source_ref=price.source_ref,
    )


def _is_effective(price: PriceListItem, event_date: date) -> bool:
    return price.effective_window.effective_from <= event_date and (
        price.effective_window.effective_to is None
        or event_date <= price.effective_window.effective_to
    )
