"""Create the initial source-backed proposal schema.

Revision ID: 20261019_0001
Revises: None
Create Date: 2026-10-19
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json(name: str, *, nullable: bool = False) -> sa.Column[object]:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def _timestamp(name: str) -> sa.Column[datetime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "source_references",
        sa.Column("source_ref_id", sa.String(128), primary_key=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("provider_source_id", sa.String(256), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        _json("location"),
        sa.Column("catalog_version", sa.String(128), nullable=False),
        sa.Column("region_spec_id", sa.String(128), nullable=False),
        sa.Column("region_spec_version", sa.String(128), nullable=False),
        _timestamp("recorded_at"),
    )
    op.create_table(
        "catalog_versions",
        sa.Column("catalog_version", sa.String(128), primary_key=True),
        _json("source_hashes"),
        _json("validation_report"),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _timestamp("created_at"),
    )
    op.create_table(
        "regional_specifications",
        sa.Column("region_spec_id", sa.String(128), primary_key=True),
        sa.Column("version", sa.String(128), primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("subdivision_code", sa.String(32)),
        sa.Column("locality", sa.String(256)),
        _json("tax_jurisdiction_ids"),
        sa.Column("timezone", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(64), nullable=False),
        _json("supported_document_languages"),
        sa.Column("currency", sa.String(3), nullable=False),
        _json("formatting_rules"),
        sa.Column("catalog_version", sa.String(128), nullable=False),
        sa.Column("regional_policy_version", sa.String(128), nullable=False),
        sa.Column("rules_version", sa.String(128), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="regional_specification_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version"], ["catalog_versions.catalog_version"]
        ),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "venues",
        sa.Column("venue_id", sa.String(128), primary_key=True),
        sa.Column("region_spec_id", sa.String(128), nullable=False),
        sa.Column("region_spec_version", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        _json("aliases"),
        _json("location_jurisdiction_ids"),
        _json("capacity_by_service_style"),
        sa.Column("template_id", sa.String(128), nullable=False),
        _json("required_fee_skus"),
        _json("restrictions"),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "menus",
        sa.Column("menu_id", sa.String(128), primary_key=True),
        sa.Column("region_spec_id", sa.String(128), nullable=False),
        sa.Column("region_spec_version", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        _json("localized_content"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        _json("event_types"),
        _json("service_styles"),
        _json("venue_ids", nullable=True),
        _json("sections"),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="menu_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "menu_items",
        sa.Column("item_id", sa.String(128), primary_key=True),
        sa.Column("menu_id", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(64), nullable=False),
        sa.Column("section", sa.String(256), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text()),
        _json("dietary_tags"),
        _json("allergen_tags"),
        sa.Column("price_basis", sa.String(128), nullable=False),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.menu_id"]),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "price_list_items",
        sa.Column("sku", sa.String(128), primary_key=True),
        sa.Column("region_spec_id", sa.String(128), primary_key=True),
        sa.Column("region_spec_version", sa.String(128), primary_key=True),
        sa.Column("locale", sa.String(64), nullable=False),
        sa.Column("description", sa.String(256), nullable=False),
        sa.Column("unit", sa.String(128), nullable=False),
        sa.Column("unit_price", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("min_qty", sa.Numeric()),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "min_qty IS NULL OR min_qty >= 0", name="price_min_quantity"
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="price_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "business_rules",
        sa.Column("rule_id", sa.String(128), primary_key=True),
        sa.Column("region_spec_id", sa.String(128), primary_key=True),
        sa.Column("region_spec_version", sa.String(128), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        _json("parameters"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="business_rule_effective_window",
        ),
        sa.ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "proposals",
        sa.Column("proposal_id", sa.String(128), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        _json("brief"),
        sa.Column("region_spec_id", sa.String(128), nullable=False),
        sa.Column("region_spec_version", sa.String(128), nullable=False),
        sa.Column("regional_policy_version", sa.String(128), nullable=False),
        sa.Column("catalog_version", sa.String(128), nullable=False),
        sa.Column("rules_version", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(128)),
        sa.Column("llm_model", sa.String(256)),
        sa.Column("locale", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(128), nullable=False),
        _json("warnings"),
        _json("needs_input"),
        sa.Column("docx_path", sa.Text()),
        sa.Column("pdf_path", sa.Text()),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.ForeignKeyConstraint(
            ["region_spec_id", "region_spec_version"],
            [
                "regional_specifications.region_spec_id",
                "regional_specifications.version",
            ],
        ),
    )
    op.create_table(
        "proposal_line_items",
        sa.Column("line_item_id", sa.String(128), primary_key=True),
        sa.Column("proposal_id", sa.String(128), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.String(128), nullable=False),
        sa.Column("unit_price", sa.Numeric(), nullable=False),
        sa.Column("total", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source_ref_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.proposal_id"]),
        sa.ForeignKeyConstraint(["source_ref_id"], ["source_references.source_ref_id"]),
    )
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.String(128), primary_key=True),
        sa.Column("proposal_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(256), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        _timestamp("occurred_at"),
        sa.ForeignKeyConstraint(["proposal_id"], ["proposals.proposal_id"]),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("proposal_line_items")
    op.drop_table("proposals")
    op.drop_table("business_rules")
    op.drop_table("price_list_items")
    op.drop_table("menu_items")
    op.drop_table("menus")
    op.drop_table("venues")
    op.drop_table("regional_specifications")
    op.drop_table("catalog_versions")
    op.drop_table("source_references")
    op.execute("DROP EXTENSION IF EXISTS vector")
