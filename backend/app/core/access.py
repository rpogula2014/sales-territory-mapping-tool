from uuid import UUID

from fastapi import HTTPException, status

from app.core.security import CurrentUser


def ensure_market_access(user: CurrentUser, market_id: UUID) -> None:
    if "*" in user.market_ids or str(market_id) in user.market_ids:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden market")
