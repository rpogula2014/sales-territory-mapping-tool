"""Shared per-seller pin color overrides for the live map.

Revision ID: 0007_seller_colors
Revises: 0006_location_assignment_dc_name
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_seller_colors"
down_revision = "0006_location_assignment_dc_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seller_colors",
        sa.Column("seller_id", sa.BigInteger(), primary_key=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("updated_by", sa.String(320), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "color ~ '^#[0-9A-Fa-f]{6}$'",
            name="ck_seller_colors_hex",
        ),
    )


def downgrade() -> None:
    op.drop_table("seller_colors")
