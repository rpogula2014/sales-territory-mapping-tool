from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.services import dc_oracle, msa_client


settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("shutdown")
async def _shutdown() -> None:
    await dc_oracle.close_pool()
    await msa_client.close_client()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
