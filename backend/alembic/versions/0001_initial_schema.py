"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entra_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("region", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "user_market_access",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), primary_key=True),
        sa.UniqueConstraint("user_id", "market_id"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("source_filename", sa.String(500), nullable=False),
        sa.Column("uploaded_by", sa.String(320), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geocode_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geocode_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_status", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("parent_dataset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sellers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("color", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("market_id", "normalized_name"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("customer_number", sa.String(255), nullable=False),
        sa.Column("account_name", sa.String(500), nullable=False),
        sa.Column("address", sa.String(500)),
        sa.Column("city", sa.String(255)),
        sa.Column("state", sa.String(64)),
        sa.Column("zip", sa.String(32)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("geocode_status", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("matched_address", sa.String(500)),
        sa.Column("suggested_seller", sa.String(255)),
        sa.Column("current_seller", sa.String(255)),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id")),
        sa.Column("mtd_sales", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ytd_sales", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ttm_volume", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tire_pros", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_program", sa.String(255)),
        sa.Column("secondary_program", sa.String(255)),
        sa.Column("market", sa.String(255)),
        sa.Column("dc", sa.String(255)),
        sa.Column("original_row_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("extra_attributes_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("assignment_changed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_by", sa.String(320)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dataset_id", "customer_number"),
    )
    op.create_table(
        "assignment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("old_seller", sa.String(255)),
        sa.Column("new_seller", sa.String(255)),
        sa.Column("old_seller_id", postgresql.UUID(as_uuid=True)),
        sa.Column("new_seller_id", postgresql.UUID(as_uuid=True)),
        sa.Column("changed_by", sa.String(320), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("change_source", sa.String(32), nullable=False),
        sa.Column("account_version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="queued"),
        sa.Column("uploaded_by", sa.String(320), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geocode_success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geocode_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2000)),
        sa.Column("warnings_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
    op.drop_table("assignment_events")
    op.drop_table("accounts")
    op.drop_table("sellers")
    op.drop_table("datasets")
    op.drop_table("user_market_access")
    op.drop_table("markets")
    op.drop_table("users")
