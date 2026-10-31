"""Version source-backed catalog records by immutable catalog snapshot.

Revision ID: 20261101_0002
Revises: 20261019_0001
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0002"
down_revision: str | Sequence[str] | None = "20261019_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOG_TABLES = (
    "venues",
    "menus",
    "menu_items",
    "price_list_items",
    "business_rules",
)


def _drop_primary_key(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            DECLARE primary_key_name text;
            BEGIN
              SELECT conname INTO primary_key_name
              FROM pg_constraint
              WHERE conrelid = '{table_name}'::regclass AND contype = 'p';
              IF primary_key_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I',
                  '{table_name}', primary_key_name);
              END IF;
            END $$;
            """
        )
    )


def _drop_menu_item_menu_foreign_key() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE foreign_key_name text;
            BEGIN
              SELECT conname INTO foreign_key_name
              FROM pg_constraint
              WHERE conrelid = 'menu_items'::regclass
                AND confrelid = 'menus'::regclass
                AND contype = 'f';
              IF foreign_key_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE menu_items DROP CONSTRAINT %I',
                  foreign_key_name);
              END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    for table_name in _CATALOG_TABLES:
        op.add_column(
            table_name,
            sa.Column("catalog_version", sa.String(length=128), nullable=True),
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name} AS catalog_record
                SET catalog_version = source_reference.catalog_version
                FROM source_references AS source_reference
                WHERE catalog_record.source_ref_id = source_reference.source_ref_id
                """
            )
        )
        op.alter_column(table_name, "catalog_version", nullable=False)

    _drop_menu_item_menu_foreign_key()
    for table_name in _CATALOG_TABLES:
        _drop_primary_key(table_name)

    op.create_primary_key("pk_venues", "venues", ["venue_id", "catalog_version"])
    op.create_primary_key("pk_menus", "menus", ["menu_id", "catalog_version"])
    op.create_primary_key("pk_menu_items", "menu_items", ["item_id", "catalog_version"])
    op.create_primary_key(
        "pk_price_list_items",
        "price_list_items",
        ["sku", "region_spec_id", "region_spec_version", "catalog_version"],
    )
    op.create_primary_key(
        "pk_business_rules",
        "business_rules",
        ["rule_id", "region_spec_id", "region_spec_version", "catalog_version"],
    )
    for table_name in _CATALOG_TABLES:
        op.create_foreign_key(
            f"fk_{table_name}_catalog_version",
            table_name,
            "catalog_versions",
            ["catalog_version"],
            ["catalog_version"],
        )
    op.create_foreign_key(
        "fk_menu_items_menu_catalog_version",
        "menu_items",
        "menus",
        ["menu_id", "catalog_version"],
        ["menu_id", "catalog_version"],
    )
    op.create_index(
        "uq_catalog_versions_one_active",
        "catalog_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    for table_name, key_columns in (
        ("venues", "venue_id"),
        ("menus", "menu_id"),
        ("menu_items", "item_id"),
        ("price_list_items", "sku, region_spec_id, region_spec_version"),
        ("business_rules", "rule_id, region_spec_id, region_spec_version"),
    ):
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                  IF EXISTS (
                    SELECT 1 FROM {table_name}
                    GROUP BY {key_columns} HAVING count(*) > 1
                  ) THEN
                    RAISE EXCEPTION
                      'cannot downgrade catalog versioning: {table_name} has '
                      'repeated business identities';
                  END IF;
                END $$;
                """
            )
        )

    op.drop_index("uq_catalog_versions_one_active", table_name="catalog_versions")
    op.drop_constraint(
        "fk_menu_items_menu_catalog_version", "menu_items", type_="foreignkey"
    )
    for table_name in _CATALOG_TABLES:
        op.drop_constraint(
            f"fk_{table_name}_catalog_version", table_name, type_="foreignkey"
        )
        _drop_primary_key(table_name)

    op.create_primary_key("pk_venues", "venues", ["venue_id"])
    op.create_primary_key("pk_menus", "menus", ["menu_id"])
    op.create_primary_key("pk_menu_items", "menu_items", ["item_id"])
    op.create_primary_key(
        "pk_price_list_items",
        "price_list_items",
        ["sku", "region_spec_id", "region_spec_version"],
    )
    op.create_primary_key(
        "pk_business_rules",
        "business_rules",
        ["rule_id", "region_spec_id", "region_spec_version"],
    )
    op.create_foreign_key(
        "fk_menu_items_menu_id_menus",
        "menu_items",
        "menus",
        ["menu_id"],
        ["menu_id"],
    )
    for table_name in _CATALOG_TABLES:
        op.drop_column(table_name, "catalog_version")
