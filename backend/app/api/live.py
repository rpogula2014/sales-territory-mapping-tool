"""Live API-driven endpoints — Oracle DC mapping + prod-msa locations + BQ metrics
+ local assignment persistence (Phase 3).

Errors:
- 503 when Oracle / BQ are not configured.
- 502 when prod-msa upstream fails.
- 409 on assignment version mismatch.
"""

from __future__ import annotations

from typing import Any

import csv
import io
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.services import (
    bq_metrics,
    dc_oracle,
    filter_schema,
    geocode_enrich,
    live_assign,
    msa_client,
    seller_colors,
)
from app.services.bq_metrics import BigQueryNotConfiguredError
from app.services.dc_oracle import OracleNotConfiguredError

router = APIRouter()

_LOCATION_FIELDS = (
    "siteUseID",
    "locationNumber",
    "customerId",
    "primaryDcId",
    "siteUseCode",
    "siteUseStatus",
    "primarySalesRepId",
    "salesrepName",
    "creditHold",
    "marketingProgAtd",
    "marketingProgVendor",
)

_METRICS_FIELDS = (
    "customer_cd",
    "dba_name",
    "address",
    "city_name",
    "state_cd",
    "county_name",
    "zip_cd",
    "latitude",
    "longitude",
    "delivery_tier",
    "tire_pros",
    "customer_group_name",
    "customer_class_name",
    "customer_channel_name",
    "mtdsales",
    "ytdsales",
    "mtdunits",
    "ytdunits",
    "priorytdsales",
)


def _oracle_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Live endpoints disabled — Oracle not configured.",
    )


def _bq_unavailable(exc: BigQueryNotConfiguredError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


def _msa_upstream_error(exc: httpx.HTTPError) -> HTTPException:
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return HTTPException(
        status_code=502,
        detail=f"prod-msa upstream error (status={status}): {exc}",
    )


async def _fetch_merged_locations(
    dc_id: int,
    *,
    with_metrics: bool,
    geocode_fill: bool,
    db: AsyncSession,
    with_assignments: bool = False,
) -> list[dict[str, Any]]:
    """Shared pipeline: msa /siteuse → filter → project → BQ merge → geocode → assignments."""
    try:
        raw = await msa_client.locations_for_dc(dc_id)
    except httpx.HTTPError as exc:
        raise _msa_upstream_error(exc) from exc

    filtered = [
        row
        for row in raw
        if row.get("siteUseCode") == "SHIP_TO" and row.get("siteUseStatus") == "A"
    ]
    locations = [{k: row.get(k) for k in _LOCATION_FIELDS} for row in filtered]

    if not with_metrics or not locations:
        if with_assignments:
            await _attach_assignments(db, locations)
        return locations

    location_cds = [
        str(loc["locationNumber"]) for loc in locations if loc.get("locationNumber") is not None
    ]
    try:
        metrics = await bq_metrics.metrics_for_locations(dc_id, location_cds)
    except BigQueryNotConfiguredError as exc:
        raise _bq_unavailable(exc) from exc

    for loc in locations:
        key = str(loc.get("locationNumber"))
        row = metrics.get(key) or {}
        for field in _METRICS_FIELDS:
            loc[field] = row.get(field)

    if geocode_fill:
        await geocode_enrich.enrich_locations(locations, db)

    if with_assignments:
        await _attach_assignments(db, locations)

    return locations


async def _attach_assignments(db: AsyncSession, locations: list[dict[str, Any]]) -> None:
    """Mutate locations in place: add a derived `assignment` block per §10a."""
    site_use_ids = [str(loc["siteUseID"]) for loc in locations if loc.get("siteUseID") is not None]
    assignments = await live_assign.assignments_for_site_use_ids(db, site_use_ids)
    for loc in locations:
        sid = str(loc.get("siteUseID"))
        assignment = assignments.get(sid)
        loc["assignment"] = live_assign.to_assignment_block(
            assignment,
            loc.get("primarySalesRepId"),
        )


@router.get("/regions")
async def get_regions() -> list[str]:
    try:
        return await dc_oracle.list_regions()
    except OracleNotConfiguredError as exc:
        raise _oracle_unavailable() from exc


@router.get("/markets")
async def get_markets(region: str | None = Query(default=None)) -> list[str]:
    try:
        return await dc_oracle.list_markets(region=region)
    except OracleNotConfiguredError as exc:
        raise _oracle_unavailable() from exc


@router.get("/dcs")
async def get_dcs(
    region: str | None = Query(default=None),
    market: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    try:
        return await dc_oracle.list_dcs(region=region, market=market)
    except OracleNotConfiguredError as exc:
        raise _oracle_unavailable() from exc


@router.get("/dcs/{dc_id}/locations")
async def get_locations(
    dc_id: int,
    withMetrics: bool = Query(default=False),  # noqa: N803
    geocodeFill: bool = Query(default=True),  # noqa: N803
    withAssignments: bool = Query(default=True),  # noqa: N803
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await _fetch_merged_locations(
        dc_id,
        with_metrics=withMetrics,
        geocode_fill=geocodeFill,
        with_assignments=withAssignments,
        db=db,
    )


@router.get("/dcs/{dc_id}/filter-schema")
async def get_filter_schema(
    dc_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = await _fetch_merged_locations(
        dc_id,
        with_metrics=True,
        geocode_fill=False,
        with_assignments=False,
        db=db,
    )
    return filter_schema.infer_schema(rows)


# === Phase 3: assignment writes ===


class AssignmentPatch(BaseModel):
    sellerId: int | None
    sellerName: str | None
    liveSellerId: int | None = None
    liveSellerName: str | None = None
    expectedVersion: int = 0
    dcId: int | None = None
    dcName: str | None = None
    market: str | None = None
    region: str | None = None
    locationNumber: str | None = None
    customerId: int | None = None


class AssignmentDelete(BaseModel):
    expectedVersion: int


class AssignmentReconfirm(BaseModel):
    liveSellerId: int | None = None
    liveSellerName: str | None = None
    expectedVersion: int


class BulkAssignBody(BaseModel):
    siteUseIds: list[str]
    sellerId: int | None
    sellerName: str | None
    dcId: int | None = None
    dcName: str | None = None
    market: str | None = None
    region: str | None = None
    liveBySite: dict[str, dict[str, Any]] = {}
    expectedVersions: dict[str, int] = {}


class BulkRevertBody(BaseModel):
    siteUseIds: list[str]
    expectedVersions: dict[str, int] = {}


@router.patch("/locations/{site_use_id}/assignment")
async def patch_assignment(
    site_use_id: str,
    payload: AssignmentPatch = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    assignment = await live_assign.upsert_assignment(
        db,
        site_use_id=site_use_id,
        new_seller_id=payload.sellerId,
        new_seller_name=payload.sellerName,
        live_seller_id=payload.liveSellerId,
        live_seller_name=payload.liveSellerName,
        expected_version=payload.expectedVersion,
        changed_by=user.email or "unknown",
        dc_id=payload.dcId,
        market=payload.market,
        region=payload.region,
        dc_name=payload.dcName,
        location_number=payload.locationNumber,
        customer_id=payload.customerId,
        change_source="single",
    )
    return live_assign.to_assignment_block(assignment, payload.liveSellerId)


@router.delete("/locations/{site_use_id}/assignment")
async def revert_assignment(
    site_use_id: str,
    payload: AssignmentDelete = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    await live_assign.delete_assignment(
        db,
        site_use_id=site_use_id,
        expected_version=payload.expectedVersion,
        changed_by=user.email or "unknown",
    )
    return {"status": "unchanged"}


@router.post("/locations/{site_use_id}/reconfirm")
async def reconfirm_assignment(
    site_use_id: str,
    payload: AssignmentReconfirm = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    assignment = await live_assign.reconfirm_assignment(
        db,
        site_use_id=site_use_id,
        live_seller_id=payload.liveSellerId,
        live_seller_name=payload.liveSellerName,
        expected_version=payload.expectedVersion,
        changed_by=user.email or "unknown",
    )
    return live_assign.to_assignment_block(assignment, payload.liveSellerId)


@router.get("/changes")
async def list_changes(
    region: str | None = Query(default=None),
    market: str | None = Query(default=None),
    dc_id: int | None = Query(default=None, alias="dcId"),
    assigned_by: str | None = Query(default=None, alias="assignedBy"),
    current_seller_id: int | None = Query(default=None, alias="currentSellerId"),
    only_changed: bool = Query(default=False, alias="onlyChanged"),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows, total = await live_assign.list_changes(
        db,
        region=region,
        market=market,
        dc_id=dc_id,
        assigned_by=assigned_by,
        current_seller_id=current_seller_id,
        only_changed=only_changed,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": [
            {
                "siteUseID": r.site_use_id,
                "locationNumber": r.location_number,
                "customerId": r.customer_id,
                "dcId": r.dc_id,
                "dcName": r.dc_name,
                "market": r.market,
                "region": r.region,
                "currentSellerId": r.current_seller_id,
                "currentSellerName": r.current_seller_name,
                "previousSellerId": r.previous_seller_id,
                "previousSellerName": r.previous_seller_name,
                "assignmentChanged": r.assignment_changed,
                "assignedBy": r.assigned_by,
                "assignedAt": r.assigned_at.isoformat() if r.assigned_at else None,
                "version": r.version,
            }
            for r in rows
        ],
    }


_CSV_COLUMNS = (
    "siteUseID",
    "locationNumber",
    "customerId",
    "dcId",
    "dcName",
    "region",
    "market",
    "previousSellerId",
    "previousSellerName",
    "currentSellerId",
    "currentSellerName",
    "assignmentChanged",
    "assignedBy",
    "assignedAt",
    "version",
)


@router.get("/changes.csv")
async def export_changes_csv(
    region: str | None = Query(default=None),
    market: str | None = Query(default=None),
    dc_id: int | None = Query(default=None, alias="dcId"),
    assigned_by: str | None = Query(default=None, alias="assignedBy"),
    current_seller_id: int | None = Query(default=None, alias="currentSellerId"),
    only_changed: bool = Query(default=False, alias="onlyChanged"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream all matching changes as CSV. No pagination — full export."""
    rows, _total = await live_assign.list_changes(
        db,
        region=region,
        market=market,
        dc_id=dc_id,
        assigned_by=assigned_by,
        current_seller_id=current_seller_id,
        only_changed=only_changed,
        limit=100_000,
        offset=0,
    )

    def iter_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CSV_COLUMNS)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for r in rows:
            writer.writerow(
                [
                    r.site_use_id,
                    r.location_number or "",
                    r.customer_id if r.customer_id is not None else "",
                    r.dc_id if r.dc_id is not None else "",
                    r.dc_name or "",
                    r.region or "",
                    r.market or "",
                    r.previous_seller_id if r.previous_seller_id is not None else "",
                    r.previous_seller_name or "",
                    r.current_seller_id if r.current_seller_id is not None else "",
                    r.current_seller_name or "",
                    "true" if r.assignment_changed else "false",
                    r.assigned_by or "",
                    r.assigned_at.isoformat() if r.assigned_at else "",
                    r.version,
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"live-changes-{ts}.csv"
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/changes/summary")
async def changes_summary(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await live_assign.changes_summary(db)


@router.post("/assignments/bulk")
async def bulk_assign(
    payload: BulkAssignBody = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ok, conflicts = await live_assign.bulk_upsert(
        db,
        site_use_ids=payload.siteUseIds,
        new_seller_id=payload.sellerId,
        new_seller_name=payload.sellerName,
        live_by_site=payload.liveBySite,
        changed_by=user.email or "unknown",
        dc_id=payload.dcId,
        market=payload.market,
        region=payload.region,
        dc_name=payload.dcName,
        expected_versions=payload.expectedVersions,
    )
    return {"ok": ok, "conflicts": conflicts}


@router.post("/changes/bulk-revert")
async def bulk_revert(
    payload: BulkRevertBody = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ok, conflicts = await live_assign.bulk_delete(
        db,
        site_use_ids=payload.siteUseIds,
        changed_by=user.email or "unknown",
        expected_versions=payload.expectedVersions,
    )
    return {"ok": ok, "conflicts": conflicts}


# === Seller color overrides (shared, map legend) ===


class SellerColorBody(BaseModel):
    color: str


@router.get("/seller-colors")
async def get_seller_colors(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    return await seller_colors.list_colors(db)


@router.put("/seller-colors/{seller_id}")
async def put_seller_color(
    seller_id: int,
    payload: SellerColorBody = Body(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    row = await seller_colors.set_color(
        db,
        seller_id=seller_id,
        color=payload.color,
        updated_by=user.email or "unknown",
    )
    return {"sellerId": str(row.seller_id), "color": row.color}


@router.delete("/seller-colors/{seller_id}", status_code=204)
async def delete_seller_color(
    seller_id: int,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 - auth gate
) -> None:
    await seller_colors.delete_color(db, seller_id=seller_id)
