from pathlib import Path

from catering_agent.config import Settings


def test_settings_have_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_port == 8080
    assert settings.log_level == "INFO"


def test_settings_accept_configured_port() -> None:
    settings = Settings(_env_file=None, app_port=9000)

    assert settings.app_port == 9000


def test_settings_build_database_url_from_file_secret(tmp_path: Path) -> None:
    secret_directory = tmp_path / "secrets"
    secret_directory.mkdir()
    database_secret = secret_directory / "db_password"
    llm_secret = secret_directory / "llm_api_key"
    database_secret.write_text("sanitized-test-password\\n")
    llm_secret.write_text("sanitized-test-key\\n")
    settings = Settings(
        _env_file=None,
        db_password_secret_file=database_secret,
        llm_api_key_secret_file=llm_secret,
    )

    assert settings.resolved_database_url() is not None
    assert "@db:5432/catering" in settings.resolved_database_url()
    assert settings.required_secrets_loaded() is True
