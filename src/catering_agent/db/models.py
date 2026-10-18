"""SQLAlchemy persistence records for the source-backed proposal domain."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from catering_agent.db.base import Base


class SourceReferenceRecord(Base):
    """Approved-source provenance referenced by catalog and proposal values."""

    __tablename__ = "source_references"

    source_ref_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(128), nullable=False)
    region_spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_spec_version: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class CatalogVersionRecord(Base):
    """A complete validated catalog import that may become active."""

    __tablename__ = "catalog_versions"

    catalog_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_hashes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class RegionalSpecificationRecord(Base):
    """A versioned regional configuration bound to approved source evidence."""

    __tablename__ = "regional_specifications"

    region_spec_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[str] = mapped_column(String(128), primary_key=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    subdivision_code: Mapped[str | None] = mapped_column(String(32))
    locality: Mapped[str | None] = mapped_column(String(256))
    tax_jurisdiction_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    timezone: Mapped[str] = mapped_column(String(128), nullable=False)
    locale: Mapped[str] = mapped_column(String(64), nullable=False)
    supported_document_languages: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    formatting_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    catalog_version: Mapped[str] = mapped_column(
        ForeignKey("catalog_versions.catalog_version"), nullable=False
    )
    regional_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="regional_specification_effective_window",
        ),
    )


class VenueRecord(Base):
    """A venue associated with one regional-specification version."""

    __tablename__ = "venues"

    venue_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_spec_version: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    location_jurisdiction_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capacity_by_service_style: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False
    )
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    required_fee_skus: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    restrictions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )


class MenuRecord(Base):
    """A region-scoped menu with date and service eligibility metadata."""

    __tablename__ = "menus"

    menu_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_spec_version: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    localized_content: Mapped[dict[str, dict[str, str]]] = mapped_column(
        JSONB, nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    event_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    service_styles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    venue_ids: Mapped[list[str] | None] = mapped_column(JSONB)
    sections: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="menu_effective_window",
        ),
        ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )


class MenuItemRecord(Base):
    """A localized menu item with source-backed descriptive text."""

    __tablename__ = "menu_items"

    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    menu_id: Mapped[str] = mapped_column(ForeignKey("menus.menu_id"), nullable=False)
    locale: Mapped[str] = mapped_column(String(64), nullable=False)
    section: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    dietary_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    allergen_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    price_basis: Mapped[str] = mapped_column(String(128), nullable=False)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )


class PriceListItemRecord(Base):
    """A Decimal-compatible source price that is never calculated by the LLM."""

    __tablename__ = "price_list_items"

    sku: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    locale: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    unit: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    min_qty: Mapped[Decimal | None] = mapped_column(Numeric)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )

    __table_args__ = (
        CheckConstraint("min_qty IS NULL OR min_qty >= 0", name="price_min_quantity"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="price_effective_window",
        ),
        ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )


class BusinessRuleRecord(Base):
    """Versioned, sourced rule parameters used by deterministic rule code."""

    __tablename__ = "business_rules"

    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    region_spec_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="business_rule_effective_window",
        ),
        ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )


class ProposalRecord(Base):
    """Reproducible proposal state, context pins, warnings, and artefact paths."""

    __tablename__ = "proposals"

    proposal_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    region_spec_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_spec_version: Mapped[str] = mapped_column(String(128), nullable=False)
    regional_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(128), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    llm_model: Mapped[str | None] = mapped_column(String(256))
    locale: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timezone: Mapped[str] = mapped_column(String(128), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    needs_input: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    docx_path: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )


class ProposalLineItemRecord(Base):
    """A priced proposal row whose source reference is mandatory."""

    __tablename__ = "proposal_line_items"

    line_item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.proposal_id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_ref_id: Mapped[str] = mapped_column(
        ForeignKey("source_references.source_ref_id"), nullable=False
    )


class AuditEventRecord(Base):
    """Append-only lifecycle evidence for proposal actions."""

    __tablename__ = "audit_events"

    audit_event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.proposal_id"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(256), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
