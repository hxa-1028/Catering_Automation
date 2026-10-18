"""Pydantic contracts for source-backed catering proposal data.

These models describe data and validation only. They do not select a region,
derive a price, or supply any business value that was not provided by a source
or reviewer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]


class SourceLocation(BaseModel):
    """A precise location within an approved provider source."""

    model_config = ConfigDict(extra="forbid")

    sheet: str | None = None
    cell_range: str | None = None
    section: str | None = None
    paragraph: str | None = None

    @model_validator(mode="after")
    def has_locator(self) -> SourceLocation:
        """Require at least one source location detail for a citation."""

        if not any((self.sheet, self.cell_range, self.section, self.paragraph)):
            raise ValueError(
                "source location requires a sheet, cell, section, or paragraph"
            )
        return self


class SourceRef(BaseModel):
    """Immutable provenance attached to a source-backed business value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref_id: Identifier
    provider: Identifier
    provider_source_id: Identifier
    content_hash: Annotated[str, Field(pattern=r"^[A-Fa-f0-9]{64}$")]
    location: SourceLocation
    catalog_version: Identifier
    region_spec_id: Identifier
    region_spec_version: Identifier


class EffectiveWindow(BaseModel):
    """An effective-date window that cannot overlap backwards."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def has_valid_date_order(self) -> EffectiveWindow:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class Money(BaseModel):
    """An explicit currency amount that rejects binary floating-point input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: Decimal
    currency: CurrencyCode

    @field_validator("amount", mode="before")
    @classmethod
    def rejects_float(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError(
                "money amounts must be Decimal or a decimal string, never float"
            )
        return value


class CatalogVersion(BaseModel):
    """An immutable catalog import version and its validation status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_version: Identifier
    source_hashes: tuple[Annotated[str, Field(pattern=r"^[A-Fa-f0-9]{64}$")], ...]
    validation_report: dict[str, Any]
    is_active: bool = False


class RegionalSpecification(BaseModel):
    """Approved regional behavior and catalog/policy binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_spec_id: Identifier
    version: Identifier
    country_code: CountryCode
    subdivision_code: str | None = None
    locality: str | None = None
    tax_jurisdiction_ids: tuple[Identifier, ...]
    timezone: Identifier
    locale: Identifier
    supported_document_languages: tuple[Identifier, ...]
    currency: CurrencyCode
    formatting_rules: dict[str, Any]
    catalog_version: Identifier
    regional_policy_version: Identifier
    rules_version: Identifier
    effective_window: EffectiveWindow
    source_ref: SourceRef


class Venue(BaseModel):
    """A region-scoped venue record sourced from approved catalog data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    venue_id: Identifier
    region_spec_id: Identifier
    region_spec_version: Identifier
    display_name: Identifier
    aliases: tuple[str, ...] = ()
    location_jurisdiction_ids: tuple[Identifier, ...]
    capacity_by_service_style: dict[Identifier, int]
    template_id: Identifier
    required_fee_skus: tuple[Identifier, ...] = ()
    restrictions: tuple[str, ...] = ()
    source_ref: SourceRef

    @field_validator("capacity_by_service_style")
    @classmethod
    def capacities_are_non_negative(
        cls, value: dict[Identifier, int]
    ) -> dict[Identifier, int]:
        if any(capacity < 0 for capacity in value.values()):
            raise ValueError("venue capacities cannot be negative")
        return value


class MenuItem(BaseModel):
    """A localized item belonging to an approved menu."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: Identifier
    menu_id: Identifier
    locale: Identifier
    section: Identifier
    name: Identifier
    description: str | None = None
    dietary_tags: tuple[Identifier, ...] = ()
    allergen_tags: tuple[Identifier, ...] = ()
    price_basis: Identifier
    source_ref: SourceRef


class Menu(BaseModel):
    """A region-scoped menu and its eligibility constraints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    menu_id: Identifier
    region_spec_id: Identifier
    region_spec_version: Identifier
    name: Identifier
    localized_content: dict[Identifier, dict[str, str]]
    effective_window: EffectiveWindow
    event_types: tuple[Identifier, ...]
    service_styles: tuple[Identifier, ...]
    venue_ids: tuple[Identifier, ...] | None = None
    sections: tuple[Identifier, ...]
    source_ref: SourceRef


class PriceListItem(BaseModel):
    """A source-backed price-list value; it contains no computed total."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: Identifier
    region_spec_id: Identifier
    region_spec_version: Identifier
    locale: Identifier
    description: Identifier
    unit: Identifier
    unit_price: Money
    min_qty: Decimal | None = None
    effective_window: EffectiveWindow
    source_ref: SourceRef

    @field_validator("min_qty")
    @classmethod
    def minimum_quantity_is_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("minimum quantity cannot be negative")
        return value


class BusinessRule(BaseModel):
    """Versioned rule metadata; its implementation remains deterministic code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: Identifier
    region_spec_id: Identifier
    region_spec_version: Identifier
    description: Identifier
    parameters: dict[str, Any]
    effective_window: EffectiveWindow
    source_ref: SourceRef


class FieldEvidence(BaseModel):
    """Evidence and extraction confidence for an EventBrief field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_span: str | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None


class EventBrief(BaseModel):
    """Partially complete event intake data; unknown values stay unset."""

    model_config = ConfigDict(extra="forbid")

    client_name: str | None = None
    client_contact: str | None = None
    event_date: date | None = None
    event_location: str | None = None
    region_spec_id: Identifier | None = None
    region_spec_version: Identifier | None = None
    venue_id: Identifier | None = None
    guest_count: int | None = Field(default=None, ge=1)
    event_type: Identifier | None = None
    service_styles: tuple[Identifier, ...] = ()
    preferred_language: Identifier | None = None
    menu_preferences: str | None = None
    dietary_requirements: str | None = None
    other_requirements: str | None = None
    field_evidence: dict[str, FieldEvidence] = Field(default_factory=dict)


class ProposalStatus(StrEnum):
    """Allowed proposal lifecycle states."""

    DRAFT_REQUESTED = "DRAFT_REQUESTED"
    BRIEF_EXTRACTED = "BRIEF_EXTRACTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    SOURCES_RESOLVED = "SOURCES_RESOLVED"
    PRICED = "PRICED"
    RENDERED = "RENDERED"
    IN_REVIEW = "IN_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NeedInput(BaseModel):
    """A blocking request for information that the system cannot invent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: Identifier
    reason: Identifier


class ProposalLineItem(BaseModel):
    """A persisted proposal line item with mandatory source provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line_item_id: Identifier
    quantity: Decimal
    unit: Identifier
    unit_price: Money
    total: Money
    source_ref: SourceRef

    @model_validator(mode="after")
    def currencies_match(self) -> ProposalLineItem:
        if self.unit_price.currency != self.total.currency:
            raise ValueError("line item unit price and total currencies must match")
        return self


class Proposal(BaseModel):
    """A reproducible proposal snapshot with pinned generation context."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: Identifier
    status: ProposalStatus
    brief: EventBrief
    region_spec_id: Identifier
    region_spec_version: Identifier
    regional_policy_version: Identifier
    catalog_version: Identifier
    rules_version: Identifier
    prompt_version: Identifier | None = None
    llm_model: Identifier | None = None
    locale: Identifier
    currency: CurrencyCode
    timezone: Identifier
    line_items: tuple[ProposalLineItem, ...] = ()
    warnings: tuple[str, ...] = ()
    needs_input: tuple[NeedInput, ...] = ()
    docx_path: str | None = None
    pdf_path: str | None = None
