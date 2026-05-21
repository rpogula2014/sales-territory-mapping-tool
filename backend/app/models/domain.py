from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.ids import new_uuid7


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    entra_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Market(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    region: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)


class UserMarketAccess(Base):
    __tablename__ = "user_market_access"
    __table_args__ = (UniqueConstraint("user_id", "market_id"),)

    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    market_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("markets.id"), primary_key=True
    )


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    name: Mapped[str] = mapped_column(String(255))
    market_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("markets.id"))
    source_filename: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[str] = mapped_column(String(320))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    geocode_success_count: Mapped[int] = mapped_column(Integer, default=0)
    geocode_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    import_status: Mapped[str] = mapped_column(String(64), default="pending")
    parent_dataset_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    accounts: Mapped[list["Account"]] = relationship(back_populates="dataset")
    market_rel: Mapped[Market] = relationship()


class Seller(TimestampMixin, Base):
    __tablename__ = "sellers"
    __table_args__ = (UniqueConstraint("market_id", "normalized_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    market_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("markets.id"))
    display_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("dataset_id", "customer_number"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("datasets.id"))
    customer_number: Mapped[str] = mapped_column(String(255))
    account_name: Mapped[str] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(64))
    zip: Mapped[str | None] = mapped_column(String(32))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geocode_status: Mapped[str] = mapped_column(String(64), default="pending")
    matched_address: Mapped[str | None] = mapped_column(String(500))
    suggested_seller: Mapped[str | None] = mapped_column(String(255))
    current_seller: Mapped[str | None] = mapped_column(String(255))
    seller_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sellers.id"))
    mtd_sales: Mapped[float] = mapped_column(Float, default=0)
    ytd_sales: Mapped[float] = mapped_column(Float, default=0)
    ttm_volume: Mapped[float] = mapped_column(Float, default=0)
    tire_pros: Mapped[bool] = mapped_column(Boolean, default=False)
    activate: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_program: Mapped[str | None] = mapped_column(String(255))
    secondary_program: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(255))
    dc: Mapped[str | None] = mapped_column(String(255))
    original_row_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    extra_attributes_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    assignment_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[str | None] = mapped_column(String(320))
    version: Mapped[int] = mapped_column(Integer, default=1)

    dataset: Mapped[Dataset] = relationship(back_populates="accounts")


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    account_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("accounts.id"))
    old_seller: Mapped[str | None] = mapped_column(String(255))
    new_seller: Mapped[str | None] = mapped_column(String(255))
    old_seller_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    new_seller_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    changed_by: Mapped[str] = mapped_column(String(320))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_source: Mapped[str] = mapped_column(String(32))
    account_version: Mapped[int] = mapped_column(Integer)


class GeocodeCache(Base):
    """Cache of Census batch-geocoder results keyed by normalized address.

    Failed matches are cached too (`matched=false`) so we don't re-call Census
    on every page load for addresses that can't be matched.
    """

    __tablename__ = "geocode_cache"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    address_key: Mapped[str] = mapped_column(String(800), unique=True, index=True)
    street: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(64))
    zip: Mapped[str] = mapped_column(String(32))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_address: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(32), default="census")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LocationAssignment(TimestampMixin, Base):
    """Current-state assignment row per site_use_id (live flow)."""

    __tablename__ = "location_assignments"
    __table_args__ = (UniqueConstraint("site_use_id", name="uq_location_assignments_site_use_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    site_use_id: Mapped[str] = mapped_column(String(64))
    location_number: Mapped[str | None] = mapped_column(String(64))
    customer_id: Mapped[int | None] = mapped_column(BigInteger)
    dc_id: Mapped[int | None] = mapped_column(Integer, index=True)
    market: Mapped[str | None] = mapped_column(String(255), index=True)
    region: Mapped[str | None] = mapped_column(String(255))
    dc_name: Mapped[str | None] = mapped_column(String(255))
    previous_seller_id: Mapped[int | None] = mapped_column(BigInteger)
    previous_seller_name: Mapped[str | None] = mapped_column(String(255))
    current_seller_id: Mapped[int | None] = mapped_column(BigInteger)
    current_seller_name: Mapped[str | None] = mapped_column(String(255))
    assignment_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by: Mapped[str | None] = mapped_column(String(320))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=0)


class LocationAssignmentEvent(Base):
    """Audit trail of every meaningful assignment change."""

    __tablename__ = "location_assignment_events"
    __table_args__ = (
        CheckConstraint(
            "change_source IN ('single','bulk','revert','reconfirm','import')",
            name="ck_assignment_events_change_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    site_use_id: Mapped[str] = mapped_column(String(64), index=True)
    old_seller_id: Mapped[int | None] = mapped_column(BigInteger)
    new_seller_id: Mapped[int | None] = mapped_column(BigInteger)
    old_seller_name: Mapped[str | None] = mapped_column(String(255))
    new_seller_name: Mapped[str | None] = mapped_column(String(255))
    changed_by: Mapped[str] = mapped_column(String(320))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_source: Mapped[str] = mapped_column(String(32))
    assignment_version: Mapped[int] = mapped_column(Integer)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("datasets.id"))
    status: Mapped[str] = mapped_column(String(64), default="queued")
    uploaded_by: Mapped[str] = mapped_column(String(320))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    geocode_success_count: Mapped[int] = mapped_column(Integer, default=0)
    geocode_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2000))
    warnings_json: Mapped[list] = mapped_column(JSONB, default=list)


class SellerColor(Base):
    """Shared per-seller pin color override for the live map view."""

    __tablename__ = "seller_colors"
    __table_args__ = (
        CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_seller_colors_hex"),
    )

    seller_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    color: Mapped[str] = mapped_column(String(7))
    updated_by: Mapped[str] = mapped_column(String(320))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

