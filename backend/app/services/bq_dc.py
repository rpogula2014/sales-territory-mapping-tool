"""Read DC / market / region rows from BigQuery.

Source: `atd-cdp-prod.raw.ebs_xxatdar_xxatdar_dc_reg_mkt_tbl` (CDC mirror of
Oracle APPS.XXATDAR_DC_REG_MKT_TBL). Same columns as the Oracle source.

Filters match the Oracle implementation: disable_date IS NULL AND
operating_unit = 82. organization_id is the numeric DC id used by prod-msa.

Results cached in-process (low churn). TTL from settings.bq_dc_cache_ttl_seconds.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from google.cloud import bigquery

from app.core.config import get_settings
from app.services.bq_metrics import BigQueryNotConfiguredError, _get_client

_TABLE = "`atd-cdp-prod.raw.ebs_xxatdar_xxatdar_dc_reg_mkt_tbl`"
_BASE_FILTER = "disable_date IS NULL AND operating_unit = 82 and market is not null and dc_name not like '%INACTIVE%'"

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = asyncio.Lock()


def _run_sync(
    client: bigquery.Client,
    sql: str,
    params: list[bigquery.ScalarQueryParameter],
) -> list[dict[str, Any]]:
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    return [dict(row) for row in job.result()]


async def _cached(key: str, sql: str, params: list[bigquery.ScalarQueryParameter]) -> Any:
    settings = get_settings()
    ttl = settings.bq_dc_cache_ttl_seconds
    now = time.time()

    async with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]

    try:
        client = await _get_client()
    except BigQueryNotConfiguredError:
        raise

    rows = await asyncio.to_thread(_run_sync, client, sql, params)

    async with _cache_lock:
        _cache[key] = (now + ttl, rows)
    return rows


async def list_regions() -> list[str]:
    sql = f"""
        SELECT DISTINCT region_name
        FROM {_TABLE}
        WHERE {_BASE_FILTER}
          AND region_name IS NOT NULL
        ORDER BY region_name
    """
    rows = await _cached("regions", sql, [])
    return [r["region_name"] for r in rows]


async def list_markets(region: str | None = None) -> list[str]:
    clauses = [_BASE_FILTER, "market IS NOT NULL"]
    params: list[bigquery.ScalarQueryParameter] = []
    key = "markets:all"
    if region:
        clauses.append("region_name = @region")
        params.append(bigquery.ScalarQueryParameter("region", "STRING", region))
        key = f"markets:{region}"

    sql = f"""
        SELECT DISTINCT market
        FROM {_TABLE}
        WHERE {" AND ".join(clauses)}
        ORDER BY market
    """  # noqa: S608 - clauses static, params bound
    rows = await _cached(key, sql, params)
    return [r["market"] for r in rows]


async def list_dcs(
    region: str | None = None,
    market: str | None = None,
) -> list[dict[str, Any]]:
    clauses = [
        _BASE_FILTER,
        "organization_id IS NOT NULL",
        "market IS NOT NULL",
    ]
    params: list[bigquery.ScalarQueryParameter] = []
    key_parts = ["dcs"]
    if region:
        clauses.append("region_name = @region")
        params.append(bigquery.ScalarQueryParameter("region", "STRING", region))
        key_parts.append(f"r={region}")
    if market:
        clauses.append("market = @market")
        params.append(bigquery.ScalarQueryParameter("market", "STRING", market))
        key_parts.append(f"m={market}")

    sql = f"""
        SELECT
            organization_id AS dc_id,
            dc_no,
            dc_name,
            region_name    AS region,
            region_no,
            market,
            market_cd
        FROM {_TABLE}
        WHERE {" AND ".join(clauses)}
        ORDER BY market, dc_name
    """  # noqa: S608 - clauses static, params bound
    return await _cached(":".join(key_parts), sql, params)


def invalidate_cache() -> None:
    _cache.clear()
