from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, get_current_user
from app.schemas import MeOut

router = APIRouter()


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {
        "id": user.email,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "markets": [],
    }
