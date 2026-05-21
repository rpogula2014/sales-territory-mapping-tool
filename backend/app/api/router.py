from fastapi import APIRouter

from app.api import accounts, auth, datasets, live, map as map_proxy, markets

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(markets.router, prefix="/markets", tags=["markets"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
api_router.include_router(map_proxy.router, prefix="/map", tags=["map"])
