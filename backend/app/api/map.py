"""MapTiler proxy — keep the API key server-side.

Endpoints:
- GET /api/map/style.json    → fetches style + rewrites every MapTiler URL.
- GET /api/map/tiles/{path}  → vector/raster tile proxy. JSON responses
                                (TileJSON) have their `tiles` URLs rewritten too.
- GET /api/map/sprite/{path} → sprite atlas proxy (PNG + JSON).
- GET /api/map/glyphs/{path} → font PBF proxy.

Categories map proxy prefix → upstream MapTiler path:
  tiles  → /tiles
  sprite → /maps/{map_id}/sprite
  glyphs → /fonts

503 if `maptiler_api_key` is unset; 502 on upstream errors.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import get_settings
from app.core.security import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

_PROXY_HEADERS = ("cache-control", "etag", "last-modified")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30.0)


def _require_key() -> str:
    key = get_settings().maptiler_api_key
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Map proxy disabled — set MAPTILER_API_KEY on the backend.",
        )
    return key


def _upstream_prefixes() -> dict[str, str]:
    """Map proxy category → upstream path prefix on api.maptiler.com."""
    settings = get_settings()
    return {
        "tiles": "/tiles",
        "sprite": f"/maps/{settings.maptiler_map_id}/sprite",
        "glyphs": "/fonts",
    }


def _rewrite_url(url: str, base_url: str) -> str:
    """Map a raw MapTiler URL into our proxy URL. Returns unchanged if not MapTiler."""
    settings = get_settings()
    upstream = settings.maptiler_base_url.rstrip("/")
    if not isinstance(url, str) or not url.startswith(upstream):
        return url
    path = url[len(upstream):].split("?", 1)[0]
    for category, prefix in _upstream_prefixes().items():
        if path.startswith(prefix):
            tail = path[len(prefix):]
            return f"{base_url}/api/map/{category}{tail}"
    # Unknown MapTiler path — leave alone (will fail loudly).
    return url


def _rewrite_style(style: dict, base_url: str) -> dict:
    for source in (style.get("sources") or {}).values():
        if isinstance(source.get("tiles"), list):
            source["tiles"] = [_rewrite_url(u, base_url) for u in source["tiles"]]
        if isinstance(source.get("url"), str):
            source["url"] = _rewrite_url(source["url"], base_url)
    if "sprite" in style:
        style["sprite"] = _rewrite_url(style["sprite"], base_url)
    if "glyphs" in style:
        style["glyphs"] = _rewrite_url(style["glyphs"], base_url)
    return style


def _rewrite_tilejson(payload: dict, base_url: str) -> dict:
    """TileJSON returned by /tiles/{tileset}.json — rewrite the `tiles` array."""
    if isinstance(payload.get("tiles"), list):
        payload["tiles"] = [_rewrite_url(u, base_url) for u in payload["tiles"]]
    return payload


def _proxy_headers(upstream: httpx.Response) -> dict[str, str]:
    return {k: upstream.headers[k] for k in _PROXY_HEADERS if k in upstream.headers}


@router.get("/style.json")
async def get_style(
    request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    key = _require_key()
    settings = get_settings()
    upstream_url = (
        f"{settings.maptiler_base_url.rstrip('/')}/maps/{settings.maptiler_map_id}/style.json"
    )
    async with _client() as client:
        try:
            r = await client.get(upstream_url, params={"key": key})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail=f"MapTiler style fetch failed: {exc}"
            ) from exc
    base_url = str(request.base_url).rstrip("/")
    return _rewrite_style(r.json(), base_url)


def _upstream_url(category: str, path: str) -> str:
    """Build the MapTiler URL for a given proxy category + tail path."""
    settings = get_settings()
    base = settings.maptiler_base_url.rstrip("/")
    if category == "tiles":
        return f"{base}/tiles/{path.lstrip('/')}"
    if category == "glyphs":
        return f"{base}/fonts/{path.lstrip('/')}"
    if category == "sprite":
        # Sprite path arrives as ".png" / "@2x.json" / "" — attach directly.
        return f"{base}/maps/{settings.maptiler_map_id}/sprite{path}"
    raise ValueError(f"unknown map proxy category: {category}")


async def _proxy_bytes(category: str, path: str, request: Request) -> Response:
    """Proxy a tile / sprite / glyph. If JSON, rewrite MapTiler URLs in body."""
    key = _require_key()
    upstream_url = _upstream_url(category, path)
    async with _client() as client:
        try:
            r = await client.get(upstream_url, params={"key": key})
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail=f"MapTiler {category} fetch failed: {exc}"
            ) from exc

    if r.status_code >= 400:
        logger.warning("MapTiler %s upstream %d for %s", category, r.status_code, path)

    content_type = r.headers.get("content-type", "")
    # TileJSON / sprite JSON responses still embed MapTiler URLs → rewrite.
    if "application/json" in content_type and r.status_code < 400:
        try:
            payload = r.json()
        except (json.JSONDecodeError, ValueError):
            payload = None
        if payload is not None:
            base_url = str(request.base_url).rstrip("/")
            if isinstance(payload, dict):
                payload = _rewrite_tilejson(payload, base_url)
            body = json.dumps(payload).encode("utf-8")
            headers = _proxy_headers(r)
            return Response(
                content=body,
                status_code=r.status_code,
                headers=headers,
                media_type="application/json",
            )

    headers = _proxy_headers(r)
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers=headers,
        media_type=content_type or None,
    )


@router.get("/tiles/{path:path}")
async def get_tile(
    path: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> Response:
    return await _proxy_bytes("tiles", path, request)


@router.get("/sprite{path:path}")
async def get_sprite(
    path: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> Response:
    # path is "" / ".png" / ".json" / "@2x.png" / "@2x.json"
    return await _proxy_bytes("sprite", path, request)


@router.get("/glyphs/{path:path}")
async def get_glyph(
    path: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> Response:
    return await _proxy_bytes("glyphs", path, request)


# Suppress unused-import warning in some IDEs.
_ = re
