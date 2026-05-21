"""Add dc_name to location_assignments for human-readable Changes UI.

Revision ID: 0006_location_assignment_dc_name
Revises: 0005_live_assignments
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_location_assignment_dc_name"
down_revision = "0005_live_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "location_assignments",
        sa.Column("dc_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("location_assignments", "dc_name")
