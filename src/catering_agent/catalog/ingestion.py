"""Strict, source-backed catalog validation and atomic persistence."""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from catering_agent.db.models import (
    BusinessRuleRecord,
    CatalogVersionRecord,
    MenuItemRecord,
    MenuRecord,
    PriceListItemRecord,
    RegionalSpecificationRecord,
    SourceReferenceRecord,
    VenueRecord,
)
from catering_agent.domain.models import (
    BusinessRule,
    Menu,
    MenuItem,
    PriceListItem,
    RegionalSpecification,
    SourceLocation,
    SourceRef,
    Venue,
)
from catering_agent.integrations.local_source import SourceDocument

_COLLECTIONS = (
    "regional_specifications",
    "venues",
    "menus",
    "menu_items",
    "price_list_items",
    "business_rules",
)


class CatalogValidationError(ValueError):
    """Raised for a source catalog that is incomplete, ambiguous, or invalid."""


@dataclass(frozen=True)
class CatalogBundle:
    """A fully validated, immutable source catalog ready for persistence."""

    catalog_version: str
    source_hashes: tuple[str, ...]
    source_refs: tuple[SourceRef, ...]
    regional_specifications: tuple[RegionalSpecification, ...]
    venues: tuple[Venue, ...]
    menus: tuple[Menu, ...]
    menu_items: tuple[MenuItem, ...]
    price_list_items: tuple[PriceListItem, ...]
    business_rules: tuple[BusinessRule, ...]

    @property
    def validation_report(self) -> dict[str, Any]:
        """Return non-sensitive counts recorded with the immutable snapshot."""

        return {
            "status": "valid",
            "counts": {
                "regional_specifications": len(self.regional_specifications),
                "venues": len(self.venues),
                "menus": len(self.menus),
                "menu_items": len(self.menu_items),
                "price_list_items": len(self.price_list_items),
                "business_rules": len(self.business_rules),
            },
        }


@dataclass(frozen=True)
class IngestResult:
    """Safe result of a successful catalog activation."""

    catalog_version: str
    validation_report: dict[str, Any]


def parse_catalog_manifest(document: SourceDocument) -> CatalogBundle:
    """Parse one local source document into a cross-record validated catalog."""

    try:
        payload = json.loads(document.content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogValidationError("catalog.json must be valid UTF-8 JSON") from error

    if not isinstance(payload, dict):
        raise CatalogValidationError("catalog.json must contain a JSON object")

    expected_keys = {"catalog_version", *_COLLECTIONS}
    received_keys = set(payload)
    if received_keys != expected_keys:
        missing = sorted(expected_keys - received_keys)
        unexpected = sorted(received_keys - expected_keys)
        raise CatalogValidationError(
            f"catalog.json keys do not match the declared schema; "
            f"missing={missing}, unexpected={unexpected}"
        )

    catalog_version = payload["catalog_version"]
    if not isinstance(catalog_version, str) or not catalog_version.strip():
        raise CatalogValidationError("catalog_version must be a non-empty string")
    if len(catalog_version) > 128:
        raise CatalogValidationError("catalog_version must be at most 128 characters")

    collections = {
        name: _read_record_collection(payload[name], name) for name in _COLLECTIONS
    }
    references: list[SourceRef] = []

    regional_specifications = _parse_records(
        collections["regional_specifications"],
        "regional_specifications",
        RegionalSpecification,
        document,
        catalog_version,
        references,
    )
    region_keys = {
        (record.region_spec_id, record.version) for record in regional_specifications
    }
    _require_unique(region_keys, len(regional_specifications), "regional specification")

    venues = _parse_records(
        collections["venues"],
        "venues",
        Venue,
        document,
        catalog_version,
        references,
    )
    _require_unique({record.venue_id for record in venues}, len(venues), "venue")
    _validate_region_references(venues, region_keys, "venue")

    menus = _parse_records(
        collections["menus"],
        "menus",
        Menu,
        document,
        catalog_version,
        references,
    )
    _require_unique({record.menu_id for record in menus}, len(menus), "menu")
    _validate_region_references(menus, region_keys, "menu")
    venue_ids = {record.venue_id for record in venues}
    for menu in menus:
        if menu.venue_ids is not None and not set(menu.venue_ids) <= venue_ids:
            raise CatalogValidationError(
                f"menu {menu.menu_id} references a venue outside this catalog"
            )

    menu_by_id = {record.menu_id: record for record in menus}
    menu_items = _parse_menu_items(
        collections["menu_items"], document, catalog_version, references, menu_by_id
    )
    _require_unique(
        {record.item_id for record in menu_items}, len(menu_items), "menu item"
    )

    price_list_items = _parse_records(
        collections["price_list_items"],
        "price_list_items",
        PriceListItem,
        document,
        catalog_version,
        references,
    )
    price_keys = {
        (record.sku, record.region_spec_id, record.region_spec_version)
        for record in price_list_items
    }
    _require_unique(price_keys, len(price_list_items), "price SKU within a region")
    _validate_region_references(price_list_items, region_keys, "price SKU")
    regional_currency = {
        (record.region_spec_id, record.version): record.currency
        for record in regional_specifications
    }
    for price in price_list_items:
        if (
            price.unit_price.currency
            != regional_currency[(price.region_spec_id, price.region_spec_version)]
        ):
            raise CatalogValidationError(
                f"price SKU {price.sku} currency does not match its "
                "regional specification"
            )

    business_rules = _parse_records(
        collections["business_rules"],
        "business_rules",
        BusinessRule,
        document,
        catalog_version,
        references,
    )
    rule_keys = {
        (record.rule_id, record.region_spec_id, record.region_spec_version)
        for record in business_rules
    }
    _require_unique(rule_keys, len(business_rules), "business rule")
    _validate_region_references(business_rules, region_keys, "business rule")

    price_skus = {record.sku for record in price_list_items}
    for venue in venues:
        if not set(venue.required_fee_skus) <= price_skus:
            raise CatalogValidationError(
                f"venue {venue.venue_id} references an unknown required fee SKU"
            )

    return CatalogBundle(
        catalog_version=catalog_version,
        source_hashes=(document.content_hash,),
        source_refs=tuple(references),
        regional_specifications=tuple(regional_specifications),
        venues=tuple(venues),
        menus=tuple(menus),
        menu_items=tuple(menu_items),
        price_list_items=tuple(price_list_items),
        business_rules=tuple(business_rules),
    )


def persist_catalog(bundle: CatalogBundle, database_url: str) -> IngestResult:
    """Write a validated snapshot and activate it atomically."""

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            existing_catalog = session.get(CatalogVersionRecord, bundle.catalog_version)
            if existing_catalog is not None:
                if (
                    existing_catalog.is_active
                    and existing_catalog.source_hashes == list(bundle.source_hashes)
                ):
                    return IngestResult(
                        catalog_version=bundle.catalog_version,
                        validation_report=existing_catalog.validation_report,
                    )
                raise CatalogValidationError(
                    "catalog_version has already been imported"
                )

            catalog_record = CatalogVersionRecord(
                catalog_version=bundle.catalog_version,
                source_hashes=list(bundle.source_hashes),
                validation_report=bundle.validation_report,
                is_active=False,
            )
            session.add(catalog_record)
            session.flush()
            session.add_all(_source_reference_records(bundle.source_refs))
            session.flush()
            session.add_all(_regional_specification_records(bundle))
            session.flush()
            session.add_all(_venue_records(bundle))
            session.add_all(_menu_records(bundle))
            session.add_all(_price_list_item_records(bundle))
            session.add_all(_business_rule_records(bundle))
            session.flush()
            session.add_all(_menu_item_records(bundle))
            session.flush()

            session.execute(
                update(CatalogVersionRecord)
                .where(CatalogVersionRecord.is_active.is_(True))
                .values(is_active=False)
            )
            catalog_record.is_active = True

        return IngestResult(
            catalog_version=bundle.catalog_version,
            validation_report=bundle.validation_report,
        )
    except SQLAlchemyError as error:
        raise CatalogValidationError(
            "catalog persistence failed; no catalog was activated"
        ) from error
    finally:
        engine.dispose()


def _read_record_collection(value: object, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise CatalogValidationError(f"{name} must be an array")
    if not value:
        raise CatalogValidationError(f"{name} must contain at least one record")
    if not all(isinstance(record, dict) for record in value):
        raise CatalogValidationError(f"{name} records must be JSON objects")
    return list(value)


def _parse_records[T: BaseModel](
    records: Sequence[dict[str, Any]],
    collection_name: str,
    model_type: type[T],
    document: SourceDocument,
    catalog_version: str,
    references: list[SourceRef],
) -> list[T]:
    parsed: list[T] = []
    for index, record in enumerate(records):
        source_ref = _new_source_ref(
            document,
            collection_name,
            index,
            _region_identifier(record),
            _region_version(record),
            catalog_version,
        )
        parsed.append(
            _parse_record(
                record,
                model_type,
                source_ref,
                collection_name,
                catalog_version=catalog_version,
            )
        )
        references.append(source_ref)
    return parsed


def _parse_menu_items(
    records: Sequence[dict[str, Any]],
    document: SourceDocument,
    catalog_version: str,
    references: list[SourceRef],
    menu_by_id: dict[str, Menu],
) -> list[MenuItem]:
    parsed: list[MenuItem] = []
    for index, record in enumerate(records):
        menu_id = record.get("menu_id")
        if not isinstance(menu_id, str) or menu_id not in menu_by_id:
            raise CatalogValidationError("menu item references an unknown menu")
        menu = menu_by_id[menu_id]
        source_ref = _new_source_ref(
            document,
            "menu_items",
            index,
            menu.region_spec_id,
            menu.region_spec_version,
            catalog_version,
        )
        parsed.append(_parse_record(record, MenuItem, source_ref, "menu_items"))
        references.append(source_ref)
    return parsed


def _parse_record[T: BaseModel](
    record: dict[str, Any],
    model_type: type[T],
    source_ref: SourceRef,
    collection: str,
    *,
    catalog_version: str | None = None,
) -> T:
    if "source_ref" in record:
        raise CatalogValidationError(f"{collection} must not supply its own source_ref")
    try:
        payload = {**record, "source_ref": source_ref}
        if model_type is RegionalSpecification:
            payload["catalog_version"] = catalog_version
        return model_type.model_validate(payload)
    except ValidationError as error:
        raise CatalogValidationError(f"invalid {collection} record") from error


def _new_source_ref(
    document: SourceDocument,
    collection: str,
    index: int,
    region_spec_id: str,
    region_spec_version: str,
    catalog_version: str,
) -> SourceRef:
    source_ref_id = (
        "local-"
        + sha256(f"{document.content_hash}:{collection}:{index}".encode()).hexdigest()
    )
    return SourceRef(
        source_ref_id=source_ref_id,
        provider=document.provider,
        provider_source_id=document.provider_source_id,
        content_hash=document.content_hash,
        location=SourceLocation(section=collection, paragraph=str(index + 1)),
        catalog_version=catalog_version,
        region_spec_id=region_spec_id,
        region_spec_version=region_spec_version,
    )


def _region_identifier(record: dict[str, Any]) -> str:
    value = record.get("region_spec_id")
    if not isinstance(value, str):
        raise CatalogValidationError("catalog record is missing region_spec_id")
    return value


def _region_version(record: dict[str, Any]) -> str:
    value = record.get("region_spec_version", record.get("version"))
    if not isinstance(value, str):
        raise CatalogValidationError("catalog record is missing region_spec_version")
    return value


def _require_unique(
    keys: Collection[object], record_count: int, description: str
) -> None:
    if len(keys) != record_count:
        raise CatalogValidationError(f"duplicate {description} records are not allowed")


def _validate_region_references(
    records: Iterable[Any], region_keys: set[tuple[str, str]], description: str
) -> None:
    for record in records:
        if (record.region_spec_id, record.region_spec_version) not in region_keys:
            raise CatalogValidationError(
                f"{description} references an unknown regional specification"
            )


def _source_reference_records(
    records: Iterable[SourceRef],
) -> list[SourceReferenceRecord]:
    return [
        SourceReferenceRecord(
            source_ref_id=record.source_ref_id,
            provider=record.provider,
            provider_source_id=record.provider_source_id,
            content_hash=record.content_hash,
            location=record.location.model_dump(exclude_none=True),
            catalog_version=record.catalog_version,
            region_spec_id=record.region_spec_id,
            region_spec_version=record.region_spec_version,
        )
        for record in records
    ]


def _regional_specification_records(
    bundle: CatalogBundle,
) -> list[RegionalSpecificationRecord]:
    return [
        RegionalSpecificationRecord(
            region_spec_id=record.region_spec_id,
            version=record.version,
            country_code=record.country_code,
            subdivision_code=record.subdivision_code,
            locality=record.locality,
            tax_jurisdiction_ids=list(record.tax_jurisdiction_ids),
            timezone=record.timezone,
            locale=record.locale,
            supported_document_languages=list(record.supported_document_languages),
            currency=record.currency,
            formatting_rules=record.formatting_rules,
            catalog_version=bundle.catalog_version,
            regional_policy_version=record.regional_policy_version,
            rules_version=record.rules_version,
            effective_from=record.effective_window.effective_from,
            effective_to=record.effective_window.effective_to,
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.regional_specifications
    ]


def _venue_records(bundle: CatalogBundle) -> list[VenueRecord]:
    return [
        VenueRecord(
            venue_id=record.venue_id,
            catalog_version=bundle.catalog_version,
            region_spec_id=record.region_spec_id,
            region_spec_version=record.region_spec_version,
            display_name=record.display_name,
            aliases=list(record.aliases),
            location_jurisdiction_ids=list(record.location_jurisdiction_ids),
            capacity_by_service_style=record.capacity_by_service_style,
            template_id=record.template_id,
            required_fee_skus=list(record.required_fee_skus),
            restrictions=list(record.restrictions),
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.venues
    ]


def _menu_records(bundle: CatalogBundle) -> list[MenuRecord]:
    return [
        MenuRecord(
            menu_id=record.menu_id,
            catalog_version=bundle.catalog_version,
            region_spec_id=record.region_spec_id,
            region_spec_version=record.region_spec_version,
            name=record.name,
            localized_content=record.localized_content,
            effective_from=record.effective_window.effective_from,
            effective_to=record.effective_window.effective_to,
            event_types=list(record.event_types),
            service_styles=list(record.service_styles),
            venue_ids=None if record.venue_ids is None else list(record.venue_ids),
            sections=list(record.sections),
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.menus
    ]


def _menu_item_records(bundle: CatalogBundle) -> list[MenuItemRecord]:
    return [
        MenuItemRecord(
            item_id=record.item_id,
            catalog_version=bundle.catalog_version,
            menu_id=record.menu_id,
            locale=record.locale,
            section=record.section,
            name=record.name,
            description=record.description,
            dietary_tags=list(record.dietary_tags),
            allergen_tags=list(record.allergen_tags),
            price_basis=record.price_basis,
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.menu_items
    ]


def _price_list_item_records(bundle: CatalogBundle) -> list[PriceListItemRecord]:
    return [
        PriceListItemRecord(
            sku=record.sku,
            region_spec_id=record.region_spec_id,
            region_spec_version=record.region_spec_version,
            catalog_version=bundle.catalog_version,
            locale=record.locale,
            description=record.description,
            unit=record.unit,
            unit_price=record.unit_price.amount,
            currency=record.unit_price.currency,
            min_qty=record.min_qty,
            effective_from=record.effective_window.effective_from,
            effective_to=record.effective_window.effective_to,
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.price_list_items
    ]


def _business_rule_records(bundle: CatalogBundle) -> list[BusinessRuleRecord]:
    return [
        BusinessRuleRecord(
            rule_id=record.rule_id,
            region_spec_id=record.region_spec_id,
            region_spec_version=record.region_spec_version,
            catalog_version=bundle.catalog_version,
            description=record.description,
            parameters=record.parameters,
            effective_from=record.effective_window.effective_from,
            effective_to=record.effective_window.effective_to,
            source_ref_id=record.source_ref.source_ref_id,
        )
        for record in bundle.business_rules
    ]
