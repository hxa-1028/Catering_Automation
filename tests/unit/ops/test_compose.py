from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_compose_declares_local_only_five_service_runtime() -> None:
    compose = (REPOSITORY_ROOT / "docker" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    for service in ("db", "migrate", "app", "worker", "docconv"):
        assert f"  {service}:" in compose

    assert "127.0.0.1:${APP_PORT}:8080" in compose
    assert "POSTGRES_PASSWORD_FILE: /run/secrets/db_password" in compose
    assert "condition: service_healthy" in compose
    assert "condition: service_completed_successfully" in compose
    assert "catering_db_data" in compose
    assert "catering_docstore" in compose
    assert "catering_net" in compose


def test_compose_pins_external_images_and_does_not_publish_internal_ports() -> None:
    compose = (REPOSITORY_ROOT / "docker" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "pgvector/pgvector:0.8.7-pg16-bookworm@sha256:" in compose
    assert "gotenberg/gotenberg:8.38.1@sha256:" in compose
    assert "5432:" not in compose
    assert "3000:" not in compose
