from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ensure_market_access
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models import Account, AssignmentEvent, Dataset, Seller
from app.schemas import AssignmentUpdateIn, BulkAssignmentIn

router = APIRouter()


@router.patch("/{account_id}/assignment")
async def update_assignment(
    account_id: UUID,
    payload: AssignmentUpdateIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    account, dataset = await _load_account_with_dataset(db, account_id)
    ensure_market_access(user, dataset.market_id)
    if account.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Stale account version",
                "accountId": str(account_id),
                "currentVersion": account.version,
                "currentSeller": account.current_seller,
            },
        )

    seller = await _load_seller(db, payload.seller_id, dataset.market_id)
    old_seller = account.current_seller
    old_seller_id = account.seller_id
    now = datetime.now(UTC)
    account.seller_id = seller.id
    account.current_seller = seller.display_name
    account.assignment_changed = True
    account.assigned_at = now
    account.assigned_by = user.email
    account.version += 1
    db.add(
        AssignmentEvent(
            account_id=account.id,
            old_seller=old_seller,
            new_seller=seller.display_name,
            old_seller_id=old_seller_id,
            new_seller_id=seller.id,
            changed_by=user.email,
            change_source="single",
            account_version=account.version,
        )
    )

    return {
        "accountId": account_id,
        "sellerId": seller.id,
        "currentSeller": seller.display_name,
        "assignmentChanged": True,
        "assignedAt": now,
        "assignedBy": user.email,
        "version": account.version,
    }


@router.post("/bulk-assignment")
async def bulk_assignment(
    payload: BulkAssignmentIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    requested = payload.accounts or []
    if not requested and payload.account_ids:
        requested = [type("BulkAccount", (), {"account_id": account_id, "version": None}) for account_id in payload.account_ids]
    if not requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No accounts selected")

    account_ids = [item.account_id for item in requested]
    result = await db.execute(
        select(Account, Dataset)
        .join(Dataset, Account.dataset_id == Dataset.id)
        .where(Account.id.in_(account_ids))
    )
    rows = result.all()
    found = {account.id: (account, dataset) for account, dataset in rows}
    missing = [str(account_id) for account_id in account_ids if account_id not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid account IDs", "failedAccountIds": missing},
        )

    market_ids = {dataset.market_id for _, dataset in found.values()}
    if len(market_ids) != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bulk assignment must stay in one market")
    market_id = next(iter(market_ids))
    ensure_market_access(user, market_id)
    seller = await _load_seller(db, payload.seller_id, market_id)

    failed_versions = []
    requested_versions = {item.account_id: item.version for item in requested}
    for account_id, (account, _) in found.items():
        expected = requested_versions.get(account_id)
        if expected is not None and account.version != expected:
            failed_versions.append(str(account_id))
    if failed_versions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Stale account versions", "failedAccountIds": failed_versions},
        )

    now = datetime.now(UTC)
    for account, _ in found.values():
        old_seller = account.current_seller
        old_seller_id = account.seller_id
        account.seller_id = seller.id
        account.current_seller = seller.display_name
        account.assignment_changed = True
        account.assigned_at = now
        account.assigned_by = user.email
        account.version += 1
        db.add(
            AssignmentEvent(
                account_id=account.id,
                old_seller=old_seller,
                new_seller=seller.display_name,
                old_seller_id=old_seller_id,
                new_seller_id=seller.id,
                changed_by=user.email,
                change_source="bulk",
                account_version=account.version,
            )
        )

    return {
        "updatedCount": len(found),
        "sellerId": seller.id,
        "seller": seller.display_name,
    }


async def _load_account_with_dataset(db: AsyncSession, account_id: UUID) -> tuple[Account, Dataset]:
    result = await db.execute(
        select(Account, Dataset).join(Dataset, Account.dataset_id == Dataset.id).where(Account.id == account_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return row[0], row[1]


async def _load_seller(db: AsyncSession, seller_id: UUID, market_id: UUID) -> Seller:
    seller = await db.get(Seller, seller_id)
    if seller is None or seller.market_id != market_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid seller")
    return seller
