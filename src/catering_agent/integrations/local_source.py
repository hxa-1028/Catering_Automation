"""Read-only local development source adapter."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class LocalSourceError(ValueError):
    """Raised when a configured local approved-source folder is unusable."""


@dataclass(frozen=True)
class SourceDocument:
    """A source document with a stable local identifier and content hash."""

    provider: str
    provider_source_id: str
    content_hash: str
    content: bytes


class LocalFilesystemSource:
    """Read the catalog manifest from an approved local directory only."""

    manifest_name = "catalog.json"

    def __init__(self, source_path: Path) -> None:
        self._source_path = source_path

    def read_catalog_manifest(self) -> SourceDocument:
        """Return the catalog manifest without changing the source directory."""

        source_path = self._resolve_manifest_path()
        try:
            content = source_path.read_bytes()
        except OSError as error:
            raise LocalSourceError(
                "could not read the local catalog manifest"
            ) from error

        if not content:
            raise LocalSourceError("the local catalog manifest is empty")

        return SourceDocument(
            provider="local_filesystem",
            provider_source_id=source_path.name,
            content_hash=sha256(content).hexdigest(),
            content=content,
        )

    def _resolve_manifest_path(self) -> Path:
        candidate = self._source_path / self.manifest_name
        if self._source_path.is_file():
            candidate = self._source_path

        if candidate.name != self.manifest_name:
            raise LocalSourceError("local ingestion requires a file named catalog.json")
        if not candidate.is_file():
            raise LocalSourceError(
                "catalog.json was not found in the local source path"
            )
        return candidate
