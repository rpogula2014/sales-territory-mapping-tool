from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MarketOut(BaseModel):
    id: UUID
    name: str


class MeOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    markets: list[MarketOut]


class DatasetOut(BaseModel):
    id: UUID
    name: str
    market_id: UUID
    import_status: str
    is_active: bool
    row_count: int


class ImportAcceptedOut(BaseModel):
    dataset_id: UUID = Field(alias="datasetId")
    import_job_id: UUID = Field(alias="importJobId")
    status: str


class ImportStatusOut(BaseModel):
    dataset_id: UUID = Field(alias="datasetId")
    import_job_id: UUID = Field(alias="importJobId")
    status: str
    row_count: int = Field(alias="rowCount")
    processed_count: int = Field(alias="processedCount")
    geocode_success_count: int = Field(alias="geocodeSuccessCount")
    geocode_failure_count: int = Field(alias="geocodeFailureCount")
    warnings: list[str]


class AssignmentUpdateIn(BaseModel):
    seller_id: UUID = Field(alias="sellerId")
    version: int


class AssignmentOut(BaseModel):
    account_id: UUID = Field(alias="accountId")
    seller_id: UUID = Field(alias="sellerId")
    current_seller: str = Field(alias="currentSeller")
    assignment_changed: bool = Field(alias="assignmentChanged")
    assigned_at: datetime = Field(alias="assignedAt")
    assigned_by: str = Field(alias="assignedBy")
    version: int


class BulkAssignmentAccountIn(BaseModel):
    account_id: UUID = Field(alias="accountId")
    version: int | None = None


class BulkAssignmentIn(BaseModel):
    seller_id: UUID = Field(alias="sellerId")
    account_ids: list[UUID] | None = Field(default=None, alias="accountIds")
    accounts: list[BulkAssignmentAccountIn] | None = None


class BulkAssignmentOut(BaseModel):
    updated_count: int = Field(alias="updatedCount")
    seller_id: UUID = Field(alias="sellerId")
    seller: str
