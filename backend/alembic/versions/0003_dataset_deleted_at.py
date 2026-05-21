"""Add deleted_at soft-delete timestamp to datasets.

Revision ID: 0003_dataset_deleted_at
Revises: 0002_market_is_active
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_dataset_deleted_at"
down_revision = "0002_market_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_datasets_deleted_at", "datasets", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_datasets_deleted_at", table_name="datasets")
    op.drop_column("datasets", "deleted_at")
