"""Persist proposal totals and proposal-level source provenance.

Revision ID: 20261128_0004
Revises: 20261122_0003
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20261128_0004"
down_revision: str | Sequence[str] | None = "20261122_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def upgrade() -> None:
    op.add_column("proposals", sa.Column("original_brief_text", sa.Text()))
    op.add_column("proposals", sa.Column("total_amount", sa.Numeric()))
    op.add_column(
        "proposals",
        sa.Column(
            "source_ref_ids",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("proposals", "source_ref_ids", server_default=None)
    _drop_primary_key("proposal_line_items")
    op.create_primary_key(
        "pk_proposal_line_items",
        "proposal_line_items",
        ["proposal_id", "line_item_id"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM proposal_line_items
                GROUP BY line_item_id HAVING count(*) > 1
              ) THEN
                RAISE EXCEPTION
                  'cannot downgrade proposal line-item identity: '
                  'repeated line IDs exist';
              END IF;
            END $$;
            """
        )
    )
    _drop_primary_key("proposal_line_items")
    op.create_primary_key(
        "pk_proposal_line_items", "proposal_line_items", ["line_item_id"]
    )
    op.drop_column("proposals", "source_ref_ids")
    op.drop_column("proposals", "total_amount")
    op.drop_column("proposals", "original_brief_text")
