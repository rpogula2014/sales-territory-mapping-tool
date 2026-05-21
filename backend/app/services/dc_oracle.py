"""Read DC / market / region rows from Oracle (XXATDAR_DC_REG_MKT_TBL).

Real columns (verified 2026-05-20 against ebsprda):
- REGION_NAME, REGION_NO, DC_NAME, DC_NO, ORGANIZATION_ID, MARKET,
  OPERATING_UNIT, DISABLE_DATE, MARKET_CD, ...

ORGANIZATION_ID is the numeric DC id that matches `primaryDcId` in the
prod-msa /siteuse/primarydcid/{dcId} endpoint. DC_NO is a 3-char text code
useful only for display. Rows with non-null DISABLE_DATE are soft-deleted.

The Oracle pool is created lazily. If credentials are missing the service
raises OracleNotConfiguredError so callers can respond with 503.
"""

from __future__ import annotations

import asyncio
from typing import Any

import oracledb

from app.core.config import get_settings

_pool: oracledb.AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


class OracleNotConfiguredError(RuntimeError):
    """Raised when Oracle credentials are missing from settings."""


async def _get_pool() -> oracledb.AsyncConnectionPool:
    global _pool
    if _pool is not None:
        return _pool

    async with _pool_lock:
        if _pool is not None:
            return _pool
        settings = get_settings()
        if not (settings.oracle_user and settings.oracle_password and settings.oracle_dsn):
            raise OracleNotConfiguredError(
                "Oracle credentials missing. Set ORACLE_USER / ORACLE_PASSWORD / ORACLE_DSN."
            )
        _pool = oracledb.create_pool_async(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
            min=settings.oracle_pool_min,
            max=settings.oracle_pool_max,
            increment=1,
        )
        return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def _rows(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    pool = await _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(sql, params)
            columns = [d[0].lower() for d in cursor.description]
            rows = await cursor.fetchall()
            return [dict(zip(columns, row, strict=True)) for row in rows]


async def list_regions() -> list[str]:
    rows = await _rows(
        """
        SELECT DISTINCT region_name
        FROM APPS.XXATDAR_DC_REG_MKT_TBL
        WHERE region_name IS NOT NULL
          AND disable_date IS NULL
          and OPERATING_UNIT = 82
        ORDER BY region_name
        """,
        {},
    )
    return [r["region_name"] for r in rows]


async def list_markets(region: str | None = None) -> list[str]:
    if region:
        rows = await _rows(
            """
            SELECT DISTINCT market
            FROM APPS.XXATDAR_DC_REG_MKT_TBL
            WHERE region_name = :region
              AND market IS NOT NULL
              AND disable_date IS NULL
              and OPERATING_UNIT = 82
            ORDER BY market
            """,
            {"region": region},
        )
    else:
        rows = await _rows(
            """
            SELECT DISTINCT market
            FROM APPS.XXATDAR_DC_REG_MKT_TBL
            WHERE market IS NOT NULL
              AND disable_date IS NULL
              and OPERATING_UNIT = 82
            ORDER BY market
            """,
            {},
        )
    return [r["market"] for r in rows]


async def list_dcs(region: str | None = None, market: str | None = None) -> list[dict[str, Any]]:
    clauses = [
        "disable_date IS NULL",
        "organization_id IS NOT NULL",
        "market IS NOT NULL",
    ]
    params: dict[str, Any] = {}
    if region:
        clauses.append("region_name = :region")
        params["region"] = region
    if market:
        clauses.append("market = :market")
        params["market"] = market

    sql = f"""
        SELECT
            organization_id AS dc_id,
            dc_no,
            dc_name,
            region_name    AS region,
            region_no,
            market,
            market_cd
        FROM APPS.XXATDAR_DC_REG_MKT_TBL
        WHERE {' AND '.join(clauses)}
       and OPERATING_UNIT = 82
        ORDER BY market, dc_name
    """  # noqa: S608 - clauses are static labels, params are bound
    return await _rows(sql, params)
