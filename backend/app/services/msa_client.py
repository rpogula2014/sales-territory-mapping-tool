"""HTTP client for prod-msa.gcp.atd-us.com — customer-location endpoints.

Holds one shared httpx.AsyncClient and a tiny in-memory TTL cache so we
don't hammer the upstream for hot DCs. No auth: internal network.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.config import get_settings

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()

# Simple per-URL cache: { url: (expires_at_epoch, payload) }.
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            settings = get_settings()
            _client = httpx.AsyncClient(
                base_url=settings.msa_base_url,
                timeout=settings.msa_timeout_seconds,
                headers={"Accept": "application/json"},
            )
        return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _get_cached(path: str) -> Any:
    settings = get_settings()
    ttl = settings.msa_cache_ttl_seconds
    now = time.time()
    async with _cache_lock:
        hit = _cache.get(path)
        if hit and hit[0] > now:
            return hit[1]
    client = await _get_client()
    response = await client.get(path)
    response.raise_for_status()
    payload = response.json()
    async with _cache_lock:
        _cache[path] = (now + ttl, payload)
    return payload


async def locations_for_dc(dc_id: int) -> list[dict[str, Any]]:
    payload = await _get_cached(f"/customerlocation/location/siteuse/primarydcid/{dc_id}")
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    if isinstance(payload, list):
        return payload
    raise ValueError(f"Unexpected response shape from msa for dc {dc_id}: {type(payload)}")
