"""Add explicit source price SKU mapping to menus.

Revision ID: 20261122_0003
Revises: 20261101_0002
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261122_0003"
down_revision: str | Sequence[str] | None = "20261101_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("menus", sa.Column("price_sku", sa.String(length=128)))


def downgrade() -> None:
    op.drop_column("menus", "price_sku")
