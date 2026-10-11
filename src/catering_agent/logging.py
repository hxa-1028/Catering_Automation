"""Structured logging with a conservative redaction processor."""

import logging
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

from catering_agent.constants import SECRET_MASK

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "client_contact",
        "client_name",
        "cookie",
        "email",
        "password",
        "phone",
        "secret",
        "token",
    }
)


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): (
                SECRET_MASK
                if str(key).lower() in _SENSITIVE_KEYS
                else _redact_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_sensitive_values(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Mask known secret and PII keys in structured event data."""

    redacted: dict[str, Any] = {}
    for key, value in event_dict.items():
        redacted[key] = (
            SECRET_MASK if key.lower() in _SENSITIVE_KEYS else _redact_value(value)
        )
    return redacted


def configure_logging(log_level: str) -> None:
    """Configure JSON logs for container and local development output."""

    level = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_sensitive_values,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
