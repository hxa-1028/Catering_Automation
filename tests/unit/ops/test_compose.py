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


def test_dockerfile_allows_the_non_root_user_to_create_the_virtual_environment() -> (
    None
):
    dockerfile = (REPOSITORY_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "RUN chown app:app /app" in dockerfile
    assert dockerfile.index("RUN chown app:app /app") < dockerfile.index("USER app")
    assert dockerfile.index("USER app") < dockerfile.index("RUN uv sync")


def test_administrator_commands_explicitly_load_the_docker_environment_file() -> None:
    command = "docker compose --env-file docker/.env -f docker/docker-compose.yml"
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    administrator_guide = (
        REPOSITORY_ROOT / "docs" / "user-manual" / "administrator.md"
    ).read_text(encoding="utf-8")

    assert command in readme
    assert command in administrator_guide
