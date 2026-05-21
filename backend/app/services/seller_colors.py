"""Shared per-seller pin color overrides — backs the live map legend picker."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import SellerColor

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex(color: str) -> str:
    if not _HEX_RE.fullmatch(color):
        raise HTTPException(status_code=400, detail="color must be #RRGGBB hex")
    return color.lower()


async def list_colors(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(select(SellerColor))).scalars().all()
    return {str(r.seller_id): r.color for r in rows}


async def set_color(
    db: AsyncSession, *, seller_id: int, color: str, updated_by: str
) -> SellerColor:
    color = _validate_hex(color)
    stmt = (
        pg_insert(SellerColor)
        .values(seller_id=seller_id, color=color, updated_by=updated_by)
        .on_conflict_do_update(
            index_elements=[SellerColor.seller_id],
            set_={"color": color, "updated_by": updated_by},
        )
        .returning(SellerColor)
    )
    row = (await db.execute(stmt)).scalar_one()
    await db.flush()
    return row


async def delete_color(db: AsyncSession, *, seller_id: int) -> None:
    await db.execute(delete(SellerColor).where(SellerColor.seller_id == seller_id))
    await db.flush()
