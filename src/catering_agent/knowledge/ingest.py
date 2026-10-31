"""Command-line entry point for approved catalog ingestion."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from catering_agent.catalog.ingestion import (
    CatalogValidationError,
    parse_catalog_manifest,
    persist_catalog,
)
from catering_agent.config import get_settings
from catering_agent.integrations.local_source import (
    LocalFilesystemSource,
    LocalSourceError,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate and atomically activate a catalog from an approved local path."""

    parser = argparse.ArgumentParser(description="Ingest an approved catalog source")
    parser.add_argument("--source", choices=("local",), required=True)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        document = LocalFilesystemSource(args.path).read_catalog_manifest()
        bundle = parse_catalog_manifest(document)
        if args.dry_run:
            print(f"Validated catalog version {bundle.catalog_version}")
            return 0

        database_url = get_settings().resolved_database_url()
        if database_url is None:
            raise CatalogValidationError("database configuration is unavailable")
        result = persist_catalog(bundle, database_url)
    except (CatalogValidationError, LocalSourceError) as error:
        parser.exit(2, f"Catalog ingestion failed: {error}\n")

    print(f"Activated catalog version {result.catalog_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
