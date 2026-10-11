from catering_agent.config import Settings


def test_settings_have_safe_development_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_port == 8080
    assert settings.log_level == "INFO"


def test_settings_accept_configured_port() -> None:
    settings = Settings(_env_file=None, app_port=9000)

    assert settings.app_port == 9000
