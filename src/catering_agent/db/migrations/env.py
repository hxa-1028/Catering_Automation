"""Alembic environment bound to the application's SQLAlchemy metadata."""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

import catering_agent.db.models  # noqa: F401
from catering_agent.config import get_settings
from catering_agent.db.alembic_config import escape_configparser_value
from catering_agent.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _configure_database_url() -> None:
    command_options = context.get_x_argument(as_dictionary=True)
    database_url = (
        command_options.get("database_url")
        or os.environ.get("CATERING_DATABASE_URL")
        or get_settings().resolved_database_url()
    )
    if database_url is None:
        raise RuntimeError(
            "CATERING_DATABASE_URL is required to run database migrations"
        )
    config.set_main_option("sqlalchemy.url", escape_configparser_value(database_url))


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    _configure_database_url()
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured PostgreSQL database."""

    _configure_database_url()
    configuration: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
