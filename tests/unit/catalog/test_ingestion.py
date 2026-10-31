from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from catering_agent.catalog.ingestion import (
    CatalogValidationError,
    parse_catalog_manifest,
)
from catering_agent.integrations.local_source import SourceDocument
from catering_agent.knowledge.ingest import main

ROOT = Path(__file__).parents[3]
SAMPLE_PATH = ROOT / "data" / "samples" / "catalog.json"


def test_sanitized_sample_catalog_has_complete_provenance() -> None:
    bundle = parse_catalog_manifest(_sample_document())

    assert bundle.catalog_version == "sample-2026-11-01"
    assert len(bundle.regional_specifications) == 1
    assert len(bundle.venues) == 3
    assert len(bundle.menus) == 5
    assert len(bundle.menu_items) == 5
    assert len(bundle.price_list_items) == 5
    assert len(bundle.source_refs) == 20
    assert all(
        source_ref.content_hash == bundle.source_hashes[0]
        for source_ref in bundle.source_refs
    )


def test_duplicate_venue_fails_before_any_persistence() -> None:
    payload = _sample_payload()
    payload["venues"].append(payload["venues"][0])

    with pytest.raises(CatalogValidationError, match="duplicate venue"):
        parse_catalog_manifest(_document_for(payload))


def test_unknown_menu_reference_fails_closed() -> None:
    payload = _sample_payload()
    payload["menu_items"][0]["menu_id"] = "unknown-menu"

    with pytest.raises(CatalogValidationError, match="unknown menu"):
        parse_catalog_manifest(_document_for(payload))


def test_float_price_is_rejected_instead_of_coerced() -> None:
    payload = _sample_payload()
    payload["price_list_items"][0]["unit_price"]["amount"] = 100.0

    with pytest.raises(CatalogValidationError, match="invalid price_list_items"):
        parse_catalog_manifest(_document_for(payload))


def test_cli_dry_run_validates_the_sample_without_database_access(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        ["--source", "local", "--path", str(SAMPLE_PATH.parent), "--dry-run"]
    )

    assert exit_code == 0
    assert "Validated catalog version sample-2026-11-01" in capsys.readouterr().out


def _sample_payload() -> dict[str, object]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _sample_document() -> SourceDocument:
    content = SAMPLE_PATH.read_bytes()
    return SourceDocument(
        provider="local_filesystem",
        provider_source_id="catalog.json",
        content_hash=sha256(content).hexdigest(),
        content=content,
    )


def _document_for(payload: dict[str, object]) -> SourceDocument:
    content = json.dumps(payload, sort_keys=True).encode("utf-8")
    return SourceDocument(
        provider="local_filesystem",
        provider_source_id="catalog.json",
        content_hash=sha256(content).hexdigest(),
        content=content,
    )
