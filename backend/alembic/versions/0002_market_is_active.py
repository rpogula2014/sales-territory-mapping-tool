"""Add is_active soft-delete flag to markets.

Revision ID: 0002_market_is_active
Revises: 0001_initial_schema
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_market_is_active"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("markets", "is_active")
