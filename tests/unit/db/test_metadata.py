from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from catering_agent.db import models  # noqa: F401
from catering_agent.db.alembic_config import escape_configparser_value
from catering_agent.db.base import Base

ROOT = Path(__file__).parents[3]


def test_metadata_contains_the_source_backed_core_tables() -> None:
    expected_tables = {
        "source_references",
        "catalog_versions",
        "regional_specifications",
        "venues",
        "menus",
        "menu_items",
        "price_list_items",
        "business_rules",
        "proposals",
        "proposal_line_items",
        "audit_events",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_source_backed_records_reference_source_references() -> None:
    source_backed_tables = {
        "regional_specifications",
        "venues",
        "menus",
        "menu_items",
        "price_list_items",
        "business_rules",
        "proposal_line_items",
    }

    for table_name in source_backed_tables:
        foreign_keys = Base.metadata.tables[table_name].foreign_keys
        assert any(
            foreign_key.target_fullname == "source_references.source_ref_id"
            for foreign_key in foreign_keys
        )


def test_region_scoped_price_and_rule_keys_do_not_collide_globally() -> None:
    expected_primary_keys = {
        "sku",
        "region_spec_id",
        "region_spec_version",
        "catalog_version",
    }
    assert {
        column.name for column in Base.metadata.tables["price_list_items"].primary_key
    } == expected_primary_keys

    assert {
        column.name for column in Base.metadata.tables["business_rules"].primary_key
    } == {"rule_id", "region_spec_id", "region_spec_version", "catalog_version"}


def test_alembic_initial_revision_is_the_current_head() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    script_directory = ScriptDirectory.from_config(config)

    assert script_directory.get_current_head() == "20261101_0002"


def test_catalog_records_are_keyed_by_immutable_catalog_version() -> None:
    expected_keys = {
        "venues": {"venue_id", "catalog_version"},
        "menus": {"menu_id", "catalog_version"},
        "menu_items": {"item_id", "catalog_version"},
        "price_list_items": {
            "sku",
            "region_spec_id",
            "region_spec_version",
            "catalog_version",
        },
        "business_rules": {
            "rule_id",
            "region_spec_id",
            "region_spec_version",
            "catalog_version",
        },
    }

    for table_name, expected_key in expected_keys.items():
        assert {
            column.name for column in Base.metadata.tables[table_name].primary_key
        } == expected_key


def test_initial_migration_creates_pgvector_and_has_a_downgrade() -> None:
    migration_path = (
        ROOT
        / "src"
        / "catering_agent"
        / "db"
        / "migrations"
        / "versions"
        / "20261019_0001_initial_schema.py"
    )
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_text
    assert "def downgrade()" in migration_text
    assert "DROP EXTENSION IF EXISTS vector" in migration_text


def test_percent_encoded_database_url_survives_alembic_config_parsing() -> None:
    database_url = "postgresql+psycopg://catering:example%3Dpassword@db:5432/catering"
    config = Config()

    config.set_main_option("sqlalchemy.url", escape_configparser_value(database_url))

    assert config.get_main_option("sqlalchemy.url") == database_url
