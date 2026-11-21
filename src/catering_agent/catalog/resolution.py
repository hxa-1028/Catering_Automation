"""Deterministic, read-only resolution over the active approved catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from catering_agent.catalog.ingestion import CatalogBundle
from catering_agent.db.models import (
    CatalogVersionRecord,
    MenuRecord,
    PriceListItemRecord,
    RegionalSpecificationRecord,
    SourceReferenceRecord,
    VenueRecord,
)
from catering_agent.domain.models import (
    EffectiveWindow,
    Identifier,
    Menu,
    Money,
    NeedInput,
    PriceListItem,
    RegionalSpecification,
    SourceLocation,
    SourceRef,
    Venue,
)


class CatalogResolutionError(RuntimeError):
    """Raised when the active catalog cannot be read as approved source data."""


class CatalogLookup(BaseModel):
    """The explicit, already-approved context used to resolve catalog choices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    region_spec_id: Identifier
    region_spec_version: Identifier
    venue_query: Identifier
    event_date: date
    event_type: Identifier
    service_styles: tuple[Identifier, ...] = Field(min_length=1)
    language: Identifier


class CatalogResolution(BaseModel):
    """A resolved catalog selection or the information still needed to continue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["RESOLVED", "NEEDS_CLARIFICATION"]
    catalog_version: Identifier
    regional_specification: RegionalSpecification | None = None
    venue: Venue | None = None
    eligible_menus: tuple[Menu, ...] = ()
    needs_input: tuple[NeedInput, ...] = ()


@dataclass(frozen=True)
class CatalogSnapshot:
    """The region, venue, and menu records from one immutable catalog version."""

    catalog_version: str
    regional_specifications: tuple[RegionalSpecification, ...]
    venues: tuple[Venue, ...]
    menus: tuple[Menu, ...]
    price_list_items: tuple[PriceListItem, ...] = ()

    @classmethod
    def from_bundle(cls, bundle: CatalogBundle) -> CatalogSnapshot:
        """Build a resolution snapshot from a validated catalog before persistence."""

        return cls(
            catalog_version=bundle.catalog_version,
            regional_specifications=bundle.regional_specifications,
            venues=bundle.venues,
            menus=bundle.menus,
            price_list_items=bundle.price_list_items,
        )


def resolve_catalog(
    snapshot: CatalogSnapshot, lookup: CatalogLookup
) -> CatalogResolution:
    """Resolve a venue and menus without inferring any regional or catalog fact."""

    regional_specifications = tuple(
        record
        for record in snapshot.regional_specifications
        if (
            record.region_spec_id == lookup.region_spec_id
            and record.version == lookup.region_spec_version
        )
    )
    if len(regional_specifications) != 1:
        return _needs_input(
            snapshot.catalog_version, "regional_specification", "unknown"
        )

    regional_specification = regional_specifications[0]
    if not _is_effective(regional_specification.effective_window, lookup.event_date):
        return _needs_input(
            snapshot.catalog_version,
            "regional_specification",
            "not_effective_on_event_date",
        )
    if lookup.language not in regional_specification.supported_document_languages:
        return _needs_input(
            snapshot.catalog_version, "proposal_language", "unsupported"
        )

    venue_matches = tuple(
        venue
        for venue in snapshot.venues
        if (
            venue.region_spec_id == lookup.region_spec_id
            and venue.region_spec_version == lookup.region_spec_version
            and _matches_venue(venue, lookup.venue_query)
        )
    )
    if not venue_matches:
        return _needs_input(
            snapshot.catalog_version, "venue", "not_in_regional_catalog"
        )
    if len(venue_matches) != 1:
        return _needs_input(snapshot.catalog_version, "venue", "ambiguous")

    venue = venue_matches[0]
    eligible_menus = tuple(
        menu
        for menu in snapshot.menus
        if _is_eligible_menu(menu, regional_specification, venue, lookup)
    )
    if not eligible_menus:
        return _needs_input(
            snapshot.catalog_version, "menu", "no_eligible_catalog_record"
        )

    return CatalogResolution(
        status="RESOLVED",
        catalog_version=snapshot.catalog_version,
        regional_specification=regional_specification,
        venue=venue,
        eligible_menus=eligible_menus,
    )


def load_active_catalog_snapshot(session: Session) -> CatalogSnapshot:
    """Load the active catalog's sourced resolution records from PostgreSQL."""

    active_catalogs = tuple(
        session.scalars(
            select(CatalogVersionRecord).where(CatalogVersionRecord.is_active.is_(True))
        )
    )
    if len(active_catalogs) != 1:
        raise CatalogResolutionError("exactly one active catalog version is required")

    catalog_version = active_catalogs[0].catalog_version
    regional_records = tuple(
        session.scalars(
            select(RegionalSpecificationRecord).where(
                RegionalSpecificationRecord.catalog_version == catalog_version
            )
        )
    )
    venue_records = tuple(
        session.scalars(
            select(VenueRecord).where(VenueRecord.catalog_version == catalog_version)
        )
    )
    menu_records = tuple(
        session.scalars(
            select(MenuRecord).where(MenuRecord.catalog_version == catalog_version)
        )
    )
    price_records = tuple(
        session.scalars(
            select(PriceListItemRecord).where(
                PriceListItemRecord.catalog_version == catalog_version
            )
        )
    )
    source_ref_ids = (
        {record.source_ref_id for record in regional_records}
        | {record.source_ref_id for record in venue_records}
        | {record.source_ref_id for record in menu_records}
        | {record.source_ref_id for record in price_records}
    )
    source_records = tuple(
        session.scalars(
            select(SourceReferenceRecord).where(
                SourceReferenceRecord.source_ref_id.in_(source_ref_ids)
            )
        )
    )
    source_refs = {
        record.source_ref_id: _source_ref(record) for record in source_records
    }

    try:
        return CatalogSnapshot(
            catalog_version=catalog_version,
            regional_specifications=tuple(
                _regional_specification(record, source_refs, catalog_version)
                for record in regional_records
            ),
            venues=tuple(
                _venue(record, source_refs, catalog_version) for record in venue_records
            ),
            menus=tuple(
                _menu(record, source_refs, catalog_version) for record in menu_records
            ),
            price_list_items=tuple(
                _price_list_item(record, source_refs, catalog_version)
                for record in price_records
            ),
        )
    except (KeyError, ValidationError, ValueError) as error:
        raise CatalogResolutionError(
            "active catalog contains invalid source records"
        ) from error


def resolve_active_catalog(
    database_url: str, lookup: CatalogLookup
) -> CatalogResolution:
    """Resolve a lookup against the active PostgreSQL catalog version."""

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            return resolve_catalog(load_active_catalog_snapshot(session), lookup)
    except SQLAlchemyError as error:
        raise CatalogResolutionError("active catalog is unavailable") from error
    finally:
        engine.dispose()


def _needs_input(catalog_version: str, field: str, reason: str) -> CatalogResolution:
    return CatalogResolution(
        status="NEEDS_CLARIFICATION",
        catalog_version=catalog_version,
        needs_input=(NeedInput(field=field, reason=reason),),
    )


def _matches_venue(venue: Venue, venue_query: str) -> bool:
    normalized_query = _normalize_exact(venue_query)
    return normalized_query in {
        _normalize_exact(venue.venue_id),
        _normalize_exact(venue.display_name),
        *(_normalize_exact(alias) for alias in venue.aliases),
    }


def _is_eligible_menu(
    menu: Menu,
    regional_specification: RegionalSpecification,
    venue: Venue,
    lookup: CatalogLookup,
) -> bool:
    return (
        menu.region_spec_id == regional_specification.region_spec_id
        and menu.region_spec_version == regional_specification.version
        and _is_effective(menu.effective_window, lookup.event_date)
        and lookup.language in menu.localized_content
        and lookup.event_type in menu.event_types
        and set(lookup.service_styles).issubset(menu.service_styles)
        and (menu.venue_ids is None or venue.venue_id in menu.venue_ids)
    )


def _is_effective(window: EffectiveWindow, on_date: date) -> bool:
    return window.effective_from <= on_date and (
        window.effective_to is None or on_date <= window.effective_to
    )


def _normalize_exact(value: str) -> str:
    return " ".join(value.split()).casefold()


def _source_ref(record: SourceReferenceRecord) -> SourceRef:
    return SourceRef(
        source_ref_id=record.source_ref_id,
        provider=record.provider,
        provider_source_id=record.provider_source_id,
        content_hash=record.content_hash,
        location=SourceLocation.model_validate(record.location),
        catalog_version=record.catalog_version,
        region_spec_id=record.region_spec_id,
        region_spec_version=record.region_spec_version,
    )


def _regional_specification(
    record: RegionalSpecificationRecord,
    source_refs: dict[str, SourceRef],
    catalog_version: str,
) -> RegionalSpecification:
    return RegionalSpecification(
        region_spec_id=record.region_spec_id,
        version=record.version,
        country_code=record.country_code,
        subdivision_code=record.subdivision_code,
        locality=record.locality,
        tax_jurisdiction_ids=tuple(record.tax_jurisdiction_ids),
        timezone=record.timezone,
        locale=record.locale,
        supported_document_languages=tuple(record.supported_document_languages),
        currency=record.currency,
        formatting_rules=record.formatting_rules,
        catalog_version=catalog_version,
        regional_policy_version=record.regional_policy_version,
        rules_version=record.rules_version,
        effective_window=EffectiveWindow(
            effective_from=record.effective_from, effective_to=record.effective_to
        ),
        source_ref=_required_source_ref(
            record.source_ref_id, source_refs, catalog_version
        ),
    )


def _venue(
    record: VenueRecord, source_refs: dict[str, SourceRef], catalog_version: str
) -> Venue:
    return Venue(
        venue_id=record.venue_id,
        region_spec_id=record.region_spec_id,
        region_spec_version=record.region_spec_version,
        display_name=record.display_name,
        aliases=tuple(record.aliases),
        location_jurisdiction_ids=tuple(record.location_jurisdiction_ids),
        capacity_by_service_style=record.capacity_by_service_style,
        template_id=record.template_id,
        required_fee_skus=tuple(record.required_fee_skus),
        restrictions=tuple(record.restrictions),
        source_ref=_required_source_ref(
            record.source_ref_id, source_refs, catalog_version
        ),
    )


def _menu(
    record: MenuRecord, source_refs: dict[str, SourceRef], catalog_version: str
) -> Menu:
    return Menu(
        menu_id=record.menu_id,
        region_spec_id=record.region_spec_id,
        region_spec_version=record.region_spec_version,
        name=record.name,
        localized_content=record.localized_content,
        effective_window=EffectiveWindow(
            effective_from=record.effective_from, effective_to=record.effective_to
        ),
        event_types=tuple(record.event_types),
        service_styles=tuple(record.service_styles),
        venue_ids=None if record.venue_ids is None else tuple(record.venue_ids),
        sections=tuple(record.sections),
        price_sku=record.price_sku,
        source_ref=_required_source_ref(
            record.source_ref_id, source_refs, catalog_version
        ),
    )


def _price_list_item(
    record: PriceListItemRecord,
    source_refs: dict[str, SourceRef],
    catalog_version: str,
) -> PriceListItem:
    return PriceListItem(
        sku=record.sku,
        region_spec_id=record.region_spec_id,
        region_spec_version=record.region_spec_version,
        locale=record.locale,
        description=record.description,
        unit=record.unit,
        unit_price=Money(amount=record.unit_price, currency=record.currency),
        min_qty=record.min_qty,
        effective_window=EffectiveWindow(
            effective_from=record.effective_from, effective_to=record.effective_to
        ),
        source_ref=_required_source_ref(
            record.source_ref_id, source_refs, catalog_version
        ),
    )


def _required_source_ref(
    source_ref_id: str, source_refs: dict[str, SourceRef], catalog_version: str
) -> SourceRef:
    source_ref = source_refs[source_ref_id]
    if source_ref.catalog_version != catalog_version:
        raise CatalogResolutionError(
            "active catalog record has stale source provenance"
        )
    return source_ref
