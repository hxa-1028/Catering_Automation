"""Runtime dependency readiness checks kept separate from HTTP routing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from catering_agent.config import Settings
from catering_agent.db.runtime import DatabaseReadinessProbe, database_is_ready


@dataclass(frozen=True)
class ReadinessStatus:
    """The safe, non-sensitive result returned by runtime dependency probes."""

    failed_checks: tuple[str, ...]

    @property
    def ready(self) -> bool:
        """Whether every required runtime dependency succeeded."""

        return not self.failed_checks


DocumentConverterProbe = Callable[[Settings], bool]
SecretProbe = Callable[[Settings], bool]


def gotenberg_is_ready(settings: Settings) -> bool:
    """Return whether the internal document conversion service is healthy."""

    request = Request(f"{settings.gotenberg_url.rstrip('/')}/health", method="GET")
    try:
        with urlopen(request, timeout=2) as response:  # noqa: S310
            return int(response.status) == 200
    except (OSError, URLError):
        return False


class RuntimeReadiness:
    """Coordinate independent readiness probes without disclosing internals."""

    def __init__(
        self,
        settings: Settings,
        *,
        database_probe: DatabaseReadinessProbe = database_is_ready,
        document_converter_probe: DocumentConverterProbe = gotenberg_is_ready,
        secret_probe: SecretProbe | None = None,
    ) -> None:
        self._settings = settings
        self._database_probe = database_probe
        self._document_converter_probe = document_converter_probe
        self._secret_probe = secret_probe or (
            lambda active_settings: active_settings.required_secrets_loaded()
        )

    def check(self) -> ReadinessStatus:
        """Run all required probes and return only their stable identifiers."""

        checks = (
            ("secrets", self._secret_probe),
            ("database", self._database_probe),
            ("document_converter", self._document_converter_probe),
        )
        failed_checks = tuple(
            name for name, probe in checks if not self._probe_safely(probe)
        )
        return ReadinessStatus(failed_checks=failed_checks)

    def _probe_safely(self, probe: Callable[[Settings], bool]) -> bool:
        try:
            return probe(self._settings)
        except Exception:  # noqa: BLE001
            return False
