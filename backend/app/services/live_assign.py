"""Local assignment persistence + status derivation (live flow Phase 3).

Status derivation (plan §10a) is computed at read time from the join of:
- Live truth: `primarySalesRepId` / `salesrepName` from prod-msa.
- Local truth: row in `location_assignments` keyed by `site_use_id`.

States:
- `unchanged`: no local row.
- `assigned`:  local current_seller_id == live seller. We saved it, source agrees.
- `changed`:   local current != live AND local previous == live. User moved; source has old seller.
- `stale`:     local current != live AND local previous != live. Source moved underneath us.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import LocationAssignment, LocationAssignmentEvent


async def assignments_for_site_use_ids(
    db: AsyncSession,
    site_use_ids: list[str],
) -> dict[str, LocationAssignment]:
    if not site_use_ids:
        return {}
    result = await db.execute(
        select(LocationAssignment).where(LocationAssignment.site_use_id.in_(site_use_ids))
    )
    return {row.site_use_id: row for row in result.scalars()}


def derive_status(
    live_seller_id: int | None,
    assignment: LocationAssignment | None,
) -> str:
    if assignment is None:
        return "unchanged"
    if assignment.current_seller_id == live_seller_id:
        return "assigned"
    if assignment.previous_seller_id == live_seller_id:
        return "changed"
    return "stale"


def to_assignment_block(
    assignment: LocationAssignment | None,
    live_seller_id: int | None,
) -> dict[str, Any]:
    status = derive_status(live_seller_id, assignment)
    if assignment is None:
        return {"status": status}
    return {
        "status": status,
        "sellerId": assignment.current_seller_id,
        "sellerName": assignment.current_seller_name,
        "previousSellerId": assignment.previous_seller_id,
        "previousSellerName": assignment.previous_seller_name,
        "assignedAt": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        "assignedBy": assignment.assigned_by,
        "version": assignment.version,
    }


async def upsert_assignment(
    db: AsyncSession,
    *,
    site_use_id: str,
    new_seller_id: int | None,
    new_seller_name: str | None,
    live_seller_id: int | None,
    live_seller_name: str | None,
    expected_version: int,
    changed_by: str,
    dc_id: int | None = None,
    market: str | None = None,
    region: str | None = None,
    dc_name: str | None = None,
    location_number: str | None = None,
    customer_id: int | None = None,
    change_source: str = "single",
) -> LocationAssignment:
    """Insert or update the assignment. Raises 409 on version mismatch."""
    existing = (
        await db.execute(
            select(LocationAssignment).where(LocationAssignment.site_use_id == site_use_id)
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if existing is None:
        if expected_version != 0:
            raise HTTPException(status_code=409, detail="No existing assignment; expected_version must be 0.")
        assignment = LocationAssignment(
            site_use_id=site_use_id,
            location_number=location_number,
            customer_id=customer_id,
            dc_id=dc_id,
            market=market,
            region=region,
            dc_name=dc_name,
            previous_seller_id=live_seller_id,
            previous_seller_name=live_seller_name,
            current_seller_id=new_seller_id,
            current_seller_name=new_seller_name,
            assignment_changed=True,
            assigned_by=changed_by,
            assigned_at=now,
            version=1,
        )
        db.add(assignment)
        db.add(
            LocationAssignmentEvent(
                site_use_id=site_use_id,
                old_seller_id=live_seller_id,
                new_seller_id=new_seller_id,
                old_seller_name=live_seller_name,
                new_seller_name=new_seller_name,
                changed_by=changed_by,
                change_source=change_source,
                assignment_version=1,
            )
        )
        await db.flush()
        return assignment

    if existing.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version mismatch: have {existing.version}, expected {expected_version}.",
        )

    old_seller_id = existing.current_seller_id
    old_seller_name = existing.current_seller_name

    # No-op if same seller — return without bumping version or writing an event.
    if old_seller_id == new_seller_id:
        return existing

    existing.previous_seller_id = old_seller_id
    existing.previous_seller_name = old_seller_name
    existing.current_seller_id = new_seller_id
    existing.current_seller_name = new_seller_name
    existing.assignment_changed = new_seller_id != live_seller_id
    existing.assigned_by = changed_by
    existing.assigned_at = now
    existing.version += 1
    # Backfill DC context if caller provided it and it's missing.
    if dc_id is not None and existing.dc_id is None:
        existing.dc_id = dc_id
    if market and not existing.market:
        existing.market = market
    if region and not existing.region:
        existing.region = region
    if dc_name and not existing.dc_name:
        existing.dc_name = dc_name

    db.add(
        LocationAssignmentEvent(
            site_use_id=site_use_id,
            old_seller_id=old_seller_id,
            new_seller_id=new_seller_id,
            old_seller_name=old_seller_name,
            new_seller_name=new_seller_name,
            changed_by=changed_by,
            change_source=change_source,
            assignment_version=existing.version,
        )
    )
    await db.flush()
    return existing


async def list_changes(
    db: AsyncSession,
    *,
    region: str | None = None,
    market: str | None = None,
    dc_id: int | None = None,
    assigned_by: str | None = None,
    current_seller_id: int | None = None,
    only_changed: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[LocationAssignment], int]:
    """Return (rows, total). Rows are local-only state — not joined with live."""
    where = []
    if region:
        where.append(LocationAssignment.region == region)
    if market:
        where.append(LocationAssignment.market == market)
    if dc_id is not None:
        where.append(LocationAssignment.dc_id == dc_id)
    if assigned_by:
        where.append(LocationAssignment.assigned_by == assigned_by)
    if current_seller_id is not None:
        where.append(LocationAssignment.current_seller_id == current_seller_id)
    if only_changed:
        where.append(LocationAssignment.assignment_changed.is_(True))

    cond = and_(*where) if where else True
    total = (
        await db.execute(select(func.count()).select_from(LocationAssignment).where(cond))
    ).scalar_one()
    rows = (
        await db.execute(
            select(LocationAssignment)
            .where(cond)
            .order_by(LocationAssignment.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def changes_summary(db: AsyncSession) -> dict[str, Any]:
    """Counts that power the dashboard tile + header counters."""
    by_region_rows = (
        await db.execute(
            select(LocationAssignment.region, func.count())
            .where(LocationAssignment.region.is_not(None))
            .group_by(LocationAssignment.region)
        )
    ).all()
    by_dc_rows = (
        await db.execute(
            select(LocationAssignment.dc_id, func.count())
            .where(LocationAssignment.dc_id.is_not(None))
            .group_by(LocationAssignment.dc_id)
        )
    ).all()
    total = (
        await db.execute(select(func.count()).select_from(LocationAssignment))
    ).scalar_one()
    changed = (
        await db.execute(
            select(func.count()).select_from(LocationAssignment).where(
                LocationAssignment.assignment_changed.is_(True)
            )
        )
    ).scalar_one()
    return {
        "total": int(total),
        "changed": int(changed),
        "byRegion": [{"region": r, "count": int(c)} for r, c in by_region_rows],
        "byDc": [{"dcId": d, "count": int(c)} for d, c in by_dc_rows],
    }


async def bulk_upsert(
    db: AsyncSession,
    *,
    site_use_ids: list[str],
    new_seller_id: int | None,
    new_seller_name: str | None,
    live_by_site: dict[str, dict[str, Any]],
    changed_by: str,
    dc_id: int | None = None,
    market: str | None = None,
    region: str | None = None,
    dc_name: str | None = None,
    expected_versions: dict[str, int] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Per-row batch upsert. Returns (ok_ids, conflicts).

    `expected_versions[sid]` lets the caller assert the version it last saw.
    On mismatch the row is appended to `conflicts` with `{siteUseId, expected, actual}`
    and skipped — other rows still apply.

    When `expected_versions` is omitted or a sid is missing from it, falls back to
    the current DB version (no race detection — backward compat).
    """
    expected_versions = expected_versions or {}
    ok: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for sid in site_use_ids:
        live = live_by_site.get(sid, {})
        existing = (
            await db.execute(
                select(LocationAssignment).where(LocationAssignment.site_use_id == sid)
            )
        ).scalar_one_or_none()
        actual = existing.version if existing else 0
        expected = expected_versions.get(sid, actual)
        if expected != actual:
            conflicts.append({"siteUseId": sid, "expected": expected, "actual": actual})
            continue
        await upsert_assignment(
            db,
            site_use_id=sid,
            new_seller_id=new_seller_id,
            new_seller_name=new_seller_name,
            live_seller_id=live.get("liveSellerId"),
            live_seller_name=live.get("liveSellerName"),
            expected_version=actual,
            changed_by=changed_by,
            dc_id=dc_id,
            market=market,
            region=region,
            dc_name=dc_name,
            location_number=live.get("locationNumber"),
            customer_id=live.get("customerId"),
            change_source="bulk",
        )
        ok.append(sid)
    return ok, conflicts


async def bulk_delete(
    db: AsyncSession,
    *,
    site_use_ids: list[str],
    changed_by: str,
    expected_versions: dict[str, int] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Per-row batch Accept-source. Returns (ok_ids, conflicts).

    `expected_versions[sid]` lets the caller assert the version it last saw.
    On mismatch the row is appended to `conflicts` and skipped. Missing rows
    are reported in `ok` (idempotent no-op).
    """
    expected_versions = expected_versions or {}
    ok: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for sid in site_use_ids:
        existing = (
            await db.execute(
                select(LocationAssignment).where(LocationAssignment.site_use_id == sid)
            )
        ).scalar_one_or_none()
        if existing is None:
            ok.append(sid)
            continue
        actual = existing.version
        expected = expected_versions.get(sid, actual)
        if expected != actual:
            conflicts.append({"siteUseId": sid, "expected": expected, "actual": actual})
            continue
        db.add(
            LocationAssignmentEvent(
                site_use_id=sid,
                old_seller_id=existing.current_seller_id,
                new_seller_id=None,
                old_seller_name=existing.current_seller_name,
                new_seller_name=None,
                changed_by=changed_by,
                change_source="revert",
                assignment_version=existing.version + 1,
            )
        )
        await db.execute(
            delete(LocationAssignment).where(LocationAssignment.site_use_id == sid)
        )
        ok.append(sid)
    await db.flush()
    return ok, conflicts


async def reconfirm_assignment(
    db: AsyncSession,
    *,
    site_use_id: str,
    live_seller_id: int | None,
    live_seller_name: str | None,
    expected_version: int,
    changed_by: str,
) -> LocationAssignment:
    """Re-anchor baseline to current upstream live seller without touching current.

    Used on `stale` rows: user keeps their local override but acknowledges the
    upstream change. After this, status flips stale → changed.
    """
    existing = (
        await db.execute(
            select(LocationAssignment).where(LocationAssignment.site_use_id == site_use_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="No assignment to reconfirm.")
    if existing.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version mismatch: have {existing.version}, expected {expected_version}.",
        )

    old_previous_id = existing.previous_seller_id
    old_previous_name = existing.previous_seller_name
    existing.previous_seller_id = live_seller_id
    existing.previous_seller_name = live_seller_name
    existing.assignment_changed = existing.current_seller_id != live_seller_id
    existing.assigned_by = changed_by
    existing.assigned_at = datetime.now(timezone.utc)
    existing.version += 1

    db.add(
        LocationAssignmentEvent(
            site_use_id=site_use_id,
            old_seller_id=old_previous_id,
            new_seller_id=live_seller_id,
            old_seller_name=old_previous_name,
            new_seller_name=live_seller_name,
            changed_by=changed_by,
            change_source="reconfirm",
            assignment_version=existing.version,
        )
    )
    await db.flush()
    return existing


async def delete_assignment(
    db: AsyncSession,
    *,
    site_use_id: str,
    expected_version: int,
    changed_by: str,
) -> None:
    """Accept-source: drop the local assignment. Writes a 'revert' audit event."""
    existing = (
        await db.execute(
            select(LocationAssignment).where(LocationAssignment.site_use_id == site_use_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        return
    if existing.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version mismatch: have {existing.version}, expected {expected_version}.",
        )

    db.add(
        LocationAssignmentEvent(
            site_use_id=site_use_id,
            old_seller_id=existing.current_seller_id,
            new_seller_id=None,
            old_seller_name=existing.current_seller_name,
            new_seller_name=None,
            changed_by=changed_by,
            change_source="revert",
            assignment_version=existing.version + 1,
        )
    )
    await db.execute(
        delete(LocationAssignment).where(LocationAssignment.site_use_id == site_use_id)
    )
    await db.flush()
