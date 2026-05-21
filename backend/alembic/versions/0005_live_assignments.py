"""Local assignment persistence for live flow (Phase 3).

Revision ID: 0005_live_assignments
Revises: 0004_geocode_cache
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0005_live_assignments"
down_revision = "0004_geocode_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_assignments",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("site_use_id", sa.String(64), nullable=False),
        sa.Column("location_number", sa.String(64), nullable=True),
        sa.Column("customer_id", sa.BigInteger, nullable=True),
        sa.Column("dc_id", sa.Integer, nullable=True),
        sa.Column("market", sa.String(255), nullable=True),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column("previous_seller_id", sa.BigInteger, nullable=True),
        sa.Column("previous_seller_name", sa.String(255), nullable=True),
        sa.Column("current_seller_id", sa.BigInteger, nullable=True),
        sa.Column("current_seller_name", sa.String(255), nullable=True),
        sa.Column("assignment_changed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("assigned_by", sa.String(320), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("site_use_id", name="uq_location_assignments_site_use_id"),
    )
    op.create_index("ix_location_assignments_dc_id", "location_assignments", ["dc_id"])
    op.create_index("ix_location_assignments_market", "location_assignments", ["market"])

    op.create_table(
        "location_assignment_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("site_use_id", sa.String(64), nullable=False),
        sa.Column("old_seller_id", sa.BigInteger, nullable=True),
        sa.Column("new_seller_id", sa.BigInteger, nullable=True),
        sa.Column("old_seller_name", sa.String(255), nullable=True),
        sa.Column("new_seller_name", sa.String(255), nullable=True),
        sa.Column("changed_by", sa.String(320), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "change_source",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("assignment_version", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "change_source IN ('single','bulk','revert','reconfirm','import')",
            name="ck_assignment_events_change_source",
        ),
    )
    op.create_index(
        "ix_location_assignment_events_site_use_id",
        "location_assignment_events",
        ["site_use_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_location_assignment_events_site_use_id", table_name="location_assignment_events")
    op.drop_table("location_assignment_events")
    op.drop_index("ix_location_assignments_market", table_name="location_assignments")
    op.drop_index("ix_location_assignments_dc_id", table_name="location_assignments")
    op.drop_table("location_assignments")
