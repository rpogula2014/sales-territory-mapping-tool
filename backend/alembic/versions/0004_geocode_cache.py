"""Geocode cache table for Census fallback lookups.

Revision ID: 0004_geocode_cache
Revises: 0003_dataset_deleted_at
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0004_geocode_cache"
down_revision = "0003_dataset_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geocode_cache",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("address_key", sa.String(800), nullable=False),
        sa.Column("street", sa.String(500), nullable=False),
        sa.Column("city", sa.String(255), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("zip", sa.String(32), nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("matched", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("matched_address", sa.String(500), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="census"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("address_key", name="uq_geocode_cache_address_key"),
    )
    op.create_index("ix_geocode_cache_address_key", "geocode_cache", ["address_key"])


def downgrade() -> None:
    op.drop_index("ix_geocode_cache_address_key", table_name="geocode_cache")
    op.drop_table("geocode_cache")
