"""Helpers for safely passing application settings into Alembic."""


def escape_configparser_value(value: str) -> str:
    """Escape percent signs so ConfigParser preserves an encoded URL exactly."""

    return value.replace("%", "%%")
