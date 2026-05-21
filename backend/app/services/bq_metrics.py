"""BigQuery metrics source — POC for Phase 2.

Pulls per-location metrics from atd-cdp-prod for a given list of location_cd
values. Local dev uses Application Default Credentials. Eventually this will
be swapped for an API call against the same dataset; the
`metrics_for_locations` function is the stable interface — callers should
not touch the BQ client directly.

Query (provided 2026-05-20):
    SELECT cd.customer_cd, cd.location_cd, cd.dba_name, cd.address,
           cd.city_name, cd.state_cd, cd.county_name, cd.zip_cd,
           cd.latitude, cd.longitude, cd.delivery_tier,
           IFNULL(cd.tire_pros_cd,'N') tire_pros,
           cust.customer_group_name, cust.customer_class_name,
           cust.customer_channel_name,
           IFNULL(sales.mtdsales, 0) mtdsales, IFNULL(sales.ytdsales, 0) ytdsales,
           IFNULL(sales.mtdunits, 0) mtdunits, IFNULL(sales.ytdunits, 0) ytdunits,
           IFNULL(sales.priorytdsales, 0) priorytdsales
    FROM `atd-cdp-prod.edw.dim_customer_location` cd
    JOIN `atd-cdp-prod.edw.dim_customer` cust
      ON cust.customer_cd = cd.customer_cd
    LEFT JOIN `atd-cdp-prod.dbt.stg_crm_account_sales` sales
      ON sales.location_cd = cd.location_cd
    WHERE cd.location_cd IN UNNEST(@location_cds)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from google.cloud import bigquery

from app.core.config import get_settings


class BigQueryNotConfiguredError(RuntimeError):
    """Raised when BigQuery client cannot be initialised."""


_client: bigquery.Client | None = None
_client_lock = asyncio.Lock()

# Cache keyed by dc_id — { dc_id: (expires_at_epoch, payload) }.
_cache: dict[int, tuple[float, dict[str, dict[str, Any]]]] = {}
_cache_lock = asyncio.Lock()


_SQL = """
SELECT
    cd.customer_cd,
    cd.location_cd,
    cd.dba_name,
    cd.address,
    cd.city_name,
    cd.state_cd,
    cd.county_name,
    cd.zip_cd,
    cd.latitude,
    cd.longitude,
    cd.delivery_tier,
    IFNULL(cd.tire_pros_cd, 'N') AS tire_pros,
    cust.customer_group_name,
    cust.customer_class_name,
    cust.customer_channel_name,
    sales.mtdsales,
    sales.ytdsales,
    sales.mtdunits,
    sales.ytdunits,
    sales.priorytdsales
FROM `atd-cdp-prod.edw.dim_customer_location` cd
JOIN `atd-cdp-prod.edw.dim_customer` cust
  ON cust.customer_cd = cd.customer_cd
LEFT JOIN `atd-cdp-prod.dbt.stg_crm_account_sales` sales
  ON sales.location_cd = cd.location_cd
WHERE cd.location_cd IN UNNEST(@location_cds)
"""


async def _get_client() -> bigquery.Client:
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            settings = get_settings()
            try:
                _client = bigquery.Client(project=settings.bigquery_project)
            except Exception as exc:  # noqa: BLE001 - surface as configured error
                raise BigQueryNotConfiguredError(
                    f"BigQuery client init failed: {exc}. "
                    "Run `gcloud auth application-default login` "
                    "or set GOOGLE_APPLICATION_CREDENTIALS."
                ) from exc
        return _client


def _run_query_sync(client: bigquery.Client, location_cds: list[str]) -> list[dict[str, Any]]:
    job = client.query(
        _SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("location_cds", "STRING", location_cds)
            ]
        ),
    )
    return [dict(row) for row in job.result()]


async def metrics_for_locations(
    dc_id: int,
    location_cds: list[str],
) -> dict[str, dict[str, Any]]:
    """Return metrics keyed by location_cd. Cache per dc_id."""
    if not location_cds:
        return {}

    settings = get_settings()
    ttl = settings.bq_metrics_cache_ttl_seconds
    now = time.time()

    async with _cache_lock:
        hit = _cache.get(dc_id)
        if hit and hit[0] > now:
            return hit[1]

    client = await _get_client()
    rows = await asyncio.to_thread(_run_query_sync, client, location_cds)
    payload: dict[str, dict[str, Any]] = {
        str(r["location_cd"]): r for r in rows if r.get("location_cd") is not None
    }

    async with _cache_lock:
        _cache[dc_id] = (now + ttl, payload)
    return payload


def invalidate_cache(dc_id: int | None = None) -> None:
    if dc_id is None:
        _cache.clear()
    else:
        _cache.pop(dc_id, None)
