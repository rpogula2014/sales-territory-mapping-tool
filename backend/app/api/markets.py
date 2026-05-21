from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models import Market

router = APIRouter()


class MarketCreateIn(BaseModel):
    name: str
    region: str | None = None


def _require_admin(user: CurrentUser) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


@router.get("")
async def list_markets(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Market).where(Market.is_active.is_(True)).order_by(Market.name)
    if "*" not in user.market_ids:
        query = query.where(Market.id.in_(user.market_ids))
    result = await db.execute(query)
    return [
        {
            "id": market.id,
            "name": market.name,
            "region": market.region,
            "is_active": market.is_active,
        }
        for market in result.scalars()
    ]


@router.post("")
async def create_market(
    payload: MarketCreateIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_admin(user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")

    existing = await db.execute(select(Market).where(Market.name == name))
    if (market := existing.scalar_one_or_none()) is not None:
        if not market.is_active:
            market.is_active = True
            market.region = payload.region or market.region
            await db.flush()
            return _serialize(market)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Market name already exists")

    market = Market(name=name, region=payload.region)
    db.add(market)
    await db.flush()
    return _serialize(market)


@router.delete("/{market_id}")
async def soft_delete_market(
    market_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_admin(user)
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    if market is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    market.is_active = False
    await db.flush()
    return _serialize(market)


def _serialize(market: Market) -> dict:
    return {
        "id": market.id,
        "name": market.name,
        "region": market.region,
        "is_active": market.is_active,
    }
