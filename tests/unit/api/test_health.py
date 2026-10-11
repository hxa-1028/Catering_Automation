from fastapi.testclient import TestClient

from catering_agent.api.main import create_app
from catering_agent.config import Settings


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
