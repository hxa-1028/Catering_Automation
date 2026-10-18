"""Database readiness checks for the container runtime."""

from __future__ import annotations

from collections.abc import Callable

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)

from catering_agent.config import Settings


def _migration_heads() -> set[str]:
    """Return the revision heads declared by this application's migration scripts."""

    return set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())


def database_is_ready(settings: Settings) -> bool:
    """Check schema, pgvector, and catalog activation using bounded DB retries."""

    database_url = settings.resolved_database_url()
    if database_url is None:
        return False

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        for attempt in Retrying(
            retry=retry_if_exception_type(SQLAlchemyError),
            stop=stop_after_delay(30),
            wait=wait_exponential(multiplier=0.25, max=5),
            reraise=True,
        ):
            with attempt, engine.connect() as connection:
                current_revisions: set[str] = set(
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalars()
                    .all()
                )
                vector_installed: bool = bool(
                    connection.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_extension "
                            "WHERE extname = 'vector')"
                        )
                    ).scalar_one()
                )
                active_catalog: bool = bool(
                    connection.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM catalog_versions "
                            "WHERE is_active)"
                        )
                    ).scalar_one()
                )
                return (
                    current_revisions == _migration_heads()
                    and vector_installed
                    and active_catalog
                )
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()

    return False


DatabaseReadinessProbe = Callable[[Settings], bool]
