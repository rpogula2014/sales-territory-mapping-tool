from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings


bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    email: str
    name: str
    role: str
    market_ids: tuple[str, ...]


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if settings.auth_disabled_for_local_dev:
        return CurrentUser(
            email="local.admin@example.com",
            name="Local Admin",
            role="admin",
            market_ids=("*",),
        )

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    # TODO: validate Microsoft Entra JWT using issuer/audience/JWKS.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="OIDC validation pending")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
