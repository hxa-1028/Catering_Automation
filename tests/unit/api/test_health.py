from fastapi.testclient import TestClient

from catering_agent.api.main import create_app
from catering_agent.config import Settings
from catering_agent.runtime import RuntimeReadiness


def test_healthz_reports_liveness() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_is_not_ready_before_dependencies_are_configured() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readyz_reports_ready_when_all_runtime_dependencies_pass() -> None:
    settings = Settings(_env_file=None)
    readiness = RuntimeReadiness(
        settings,
        database_probe=lambda _: True,
        document_converter_probe=lambda _: True,
        secret_probe=lambda _: True,
    )
    client = TestClient(create_app(settings, runtime_readiness=readiness))

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readyz_reports_only_failed_check_identifiers() -> None:
    settings = Settings(_env_file=None)
    readiness = RuntimeReadiness(
        settings,
        database_probe=lambda _: False,
        document_converter_probe=lambda _: True,
        secret_probe=lambda _: False,
    )
    client = TestClient(create_app(settings, runtime_readiness=readiness))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "failed_checks": ["secrets", "database"],
    }
