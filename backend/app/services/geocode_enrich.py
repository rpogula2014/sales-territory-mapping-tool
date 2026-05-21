"""Enrich locations with lat/lng via Postgres cache + Census fallback.

Lookup order per row:
1. BQ-provided latitude/longitude (kept as-is; tagged `lat_source='source'`).
2. Postgres `geocode_cache` row keyed by normalized address.
3. Census batch geocoder (one call for all misses), persisted into cache.

Cache stores misses too — `matched=false` rows prevent re-calling Census
forever for addresses that won't geocode.

Census results are rejected when the matched address's state doesn't equal
the requested state (cheap sanity check against pin-on-wrong-coast bugs).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.domain import GeocodeCache
from app.services.geocoder import CensusBatchGeocoder, GeocodeInput

logger = logging.getLogger(__name__)

_KEY_FIELDS = ("address", "city_name", "state_cd", "zip_cd")


def _address_key(street: str, city: str, state: str, zip_: str) -> str:
    parts = [street, city, state, zip_]
    return "|".join(p.strip().upper() for p in parts)


def _row_has_address(row: dict[str, Any]) -> bool:
    return all(row.get(field) for field in _KEY_FIELDS)


def _row_has_coords(row: dict[str, Any]) -> bool:
    return row.get("latitude") is not None and row.get("longitude") is not None


async def enrich_locations(
    rows: list[dict[str, Any]],
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Mutate rows in place: fill lat/lng + add lat_source. Returns same list."""
    for row in rows:
        row["lat_source"] = "source" if _row_has_coords(row) else None

    total = len(rows)
    missing_coords = sum(1 for r in rows if not _row_has_coords(r))
    missing_addr_too = sum(
        1 for r in rows if not _row_has_coords(r) and not _row_has_address(r)
    )
    missing = [r for r in rows if not _row_has_coords(r) and _row_has_address(r)]

    logger.info(
        "enrich_locations: total=%d had_bq_coords=%d missing_coords=%d "
        "missing_coords_and_address=%d candidates_for_census=%d",
        total,
        total - missing_coords,
        missing_coords,
        missing_addr_too,
        len(missing),
    )

    if not missing:
        return rows

    # Build per-row key for fast assignment back.
    keyed: list[tuple[dict[str, Any], str]] = []
    for r in missing:
        key = _address_key(r["address"], r["city_name"], r["state_cd"], r["zip_cd"])
        keyed.append((r, key))

    unique_keys = list({k for _, k in keyed})

    # 1) Cache lookup.
    result = await db.execute(
        select(GeocodeCache).where(GeocodeCache.address_key.in_(unique_keys))
    )
    cached: dict[str, GeocodeCache] = {row.address_key: row for row in result.scalars()}

    # Fill from cache.
    for row, key in keyed:
        hit = cached.get(key)
        if hit and hit.matched and hit.latitude is not None and hit.longitude is not None:
            row["latitude"] = hit.latitude
            row["longitude"] = hit.longitude
            row["lat_source"] = hit.source

    # 2) Census for keys not in cache.
    misses = [(row, key) for row, key in keyed if key not in cached]
    if not misses:
        return rows

    # Deduplicate: same address may appear on multiple rows.
    inputs_by_key: dict[str, GeocodeInput] = {}
    for row, key in misses:
        if key in inputs_by_key:
            continue
        inputs_by_key[key] = GeocodeInput(
            unique_id=key,
            street=str(row["address"]),
            city=str(row["city_name"]),
            state=str(row["state_cd"]),
            zip=str(row["zip_cd"]),
        )

    settings = get_settings()
    geocoder = CensusBatchGeocoder(
        batch_url=settings.census_batch_url,
        chunk_size=settings.geocode_chunk_size,
    )
    logger.info(
        "enrich_locations: calling Census batch geocoder unique_addresses=%d",
        len(inputs_by_key),
    )
    try:
        results = await geocoder.geocode(list(inputs_by_key.values()))
    except Exception:
        logger.exception("Census geocoder call failed; skipping cache write")
        return rows
    by_key = {r.unique_id: r for r in results}
    matched_count = sum(1 for r in results if r.matched)
    logger.info(
        "enrich_locations: census returned matched=%d of %d",
        matched_count,
        len(results),
    )

    # Persist + apply.
    insert_payloads: list[dict[str, Any]] = []
    for row, key in misses:
        inp = inputs_by_key[key]
        res = by_key.get(key)
        matched = bool(res and res.matched and res.latitude is not None)

        # State-mismatch reject — pins-on-wrong-coast guard.
        if matched and res and res.matched_address:
            if inp.state.upper() not in res.matched_address.upper():
                matched = False

        insert_payloads.append(
            {
                "address_key": key,
                "street": inp.street,
                "city": inp.city,
                "state": inp.state,
                "zip": inp.zip,
                "latitude": res.latitude if matched and res else None,
                "longitude": res.longitude if matched and res else None,
                "matched": matched,
                "matched_address": res.matched_address if res else None,
                "source": "census",
            }
        )
        if matched and res:
            row["latitude"] = res.latitude
            row["longitude"] = res.longitude
            row["lat_source"] = "census"

    if insert_payloads:
        # Dedupe by address_key in this batch.
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for payload in insert_payloads:
            if payload["address_key"] in seen:
                continue
            seen.add(payload["address_key"])
            deduped.append(payload)

        stmt = pg_insert(GeocodeCache).values(deduped)
        stmt = stmt.on_conflict_do_nothing(index_elements=["address_key"])
        await db.execute(stmt)
        await db.commit()

    return rows
