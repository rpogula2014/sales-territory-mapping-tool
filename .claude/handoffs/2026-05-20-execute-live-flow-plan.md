# Execute Live API-Driven Flow Plan

Slug: `execute-live-flow-plan` · Created: 2026-05-20 · Working dir: `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool`

## 1. Primary Request and Intent

User pivoted from the Excel-import flow to a **live, API-driven flow**:

- Pull DC / market / region from Oracle table `APPS.XXATDAR_DC_REG_MKT_TBL`.
- Pull locations under a DC from `https://prod-msa.gcp.atd-us.com/customerlocation/location/siteuse/primarydcid/{dcId}` (no auth, internal network).
- Pull per-location metrics + lat/lng from a metrics endpoint (path TBD — fields **are** confirmed in §5a of `plan-live.md`).
- Pull per-location detail (carries seller candidate fields) from another endpoint (path TBD).
- User assigns a new seller. Saves persist to **local Postgres only** (audit log). No write-back to source.
- Keep the Excel flow as a fallback (do not delete those tables).

A full plan was authored at `plan-live.md`. **No live-flow code has been written yet.** Several Q&A rounds locked the design decisions captured in that doc.

Earlier in the same session (already completed, not part of this handoff):

- Full Angular refactor to atd-angular standards (folder-per-component, external html/scss, atd- selector prefix, design tokens, NgRx store, lazy routes).
- `/admin/markets` create + soft-delete page.
- `/home` dashboard + persistent left-rail nav (icon rail, 56→220 px on hover).
- Dataset soft-delete (`datasets.deleted_at`) + inline remove on market picker cards.
- Bug fixes: sidebar overflow, nav-item spacing.

## 2. Key Technical Concepts

- **FastAPI + SQLAlchemy async + Alembic** backend.
- **Angular 20** standalone components, NgRx (store/effects/devtools), OnPush, signals, lazy `loadComponent` routes.
- **atd-angular** skill standards: folder-per-component, `atd-` prefix, external templates/styles, `inject()` DI, modern control flow.
- **Design tokens** in `src/styles.scss` (CSS custom properties for color/space/radius/font).
- **oracledb** thin-mode async driver (about to be added).
- **httpx AsyncClient** singleton with TTL cache for prod-msa proxy.
- **Optimistic locking** via `version` column for assignment writes.
- **Soft delete pattern**: `is_active` for markets/sellers; `deleted_at` for datasets (avoids overloading `is_active` which already denotes "current active dataset version").
- **Status derivation pattern** (plan §10a): every location row carries both live + assigned seller, with a derived status (`unchanged | assigned | changed | stale`).
- **Auto-inferred filter schema** (plan §10b): no hardcoded filters; backend samples payload, infers control type per field, returns `/api/live/dcs/{dcId}/filter-schema`. UI renders dynamically.

## 3. Files and Code Sections

### `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool/plan-live.md`

- **Why important**: Authoritative plan. Sections 1–12 + 5a, 7a, 10a, 10b. Read this first in the next session.
- **Status**: Awaiting `approve plan` from user. Plan now includes:
  - §3 open items (metrics URL, sellers URL, Oracle creds, column names of `XXATDAR_DC_REG_MKT_TBL`, expected DC sizes, caching policy)
  - §5 Phase 1 endpoints (regions / markets / dcs / dcs/{id}/locations)
  - §5a confirmed metrics field set (just added — see "Current Work")
  - §6 Phase 2 deferred endpoints
  - §7 Phase 3 assignment endpoints
  - §7a existing-table relevance map (only `users` shared with live)
  - §8 new tables `location_assignments` + `location_assignment_events`
  - §9 frontend layout (NgRx live store, `/live/dcs`, `/live/dcs/:dcId/locations`)
  - §10a change tracking (Surface A inline + Surface B `/live/changes`)
  - §10b dynamic filter schema

### `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool/backend/pyproject.toml`

- **Why important**: `oracledb>=2.4.0` already added to dependencies; needs `uv sync` (or equivalent) before Phase 1 runs.
- **Changes made**: One line added.
- **Code snippet**:
  ```toml
  dependencies = [
      "alembic>=1.13.0",
      "asyncpg>=0.29.0",
      "fastapi>=0.115.0",
      "httpx>=0.27.0",
      "oracledb>=2.4.0",
      "openpyxl>=3.1.0",
      ...
  ]
  ```

### `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool/backend/app/core/config.py`

- **Why important**: Oracle + MSA settings added. Will be empty by default → live endpoints must return 503 with friendly message when unconfigured.
- **Changes made**: Added 8 settings.
- **Code snippet**:
  ```python
  oracle_user: str = ""
  oracle_password: str = ""
  oracle_dsn: str = ""  # e.g. "host:1521/service" or full TNS
  oracle_pool_min: int = 1
  oracle_pool_max: int = 4

  msa_base_url: str = "https://prod-msa.gcp.atd-us.com"
  msa_timeout_seconds: float = 15.0
  msa_cache_ttl_seconds: int = 300
  ```

### `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool/backend/app/services/dc_oracle.py`

- **Why important**: Full async Oracle pool + query module. **Written but not yet referenced by any router.** Will compile and import cleanly once `oracledb` is installed.
- **Changes made**: New file. Exports `list_regions()`, `list_markets(region=None)`, `list_dcs(region=None, market=None)`, `close_pool()`, `OracleNotConfiguredError`.
- **Code snippet** (key bits):
  ```python
  _pool: oracledb.AsyncConnectionPool | None = None

  async def _get_pool() -> oracledb.AsyncConnectionPool:
      # lazy init, raises OracleNotConfiguredError if env missing

  async def list_dcs(region=None, market=None):
      sql = "SELECT * FROM APPS.XXATDAR_DC_REG_MKT_TBL WHERE 1=1 ..."
      return await _rows(sql, params)
  ```
- **Caveat**: Assumes column names `region`, `market`, `dc_name`. User has **not** confirmed exact column names — verify against the real table before considering Phase 1 done.

### `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool/backend/app/services/msa_client.py`

- **Status**: File creation was **interrupted by the user** before it landed on disk. **Re-write it in the next session.** Intended content was:
  ```python
  """HTTP client for prod-msa.gcp.atd-us.com — customer-location endpoints.

  Holds one shared httpx.AsyncClient and a tiny in-memory TTL cache so we
  don't hammer the upstream for hot DCs. No auth: internal network.
  """

  from __future__ import annotations
  import asyncio, time
  from typing import Any
  import httpx
  from app.core.config import get_settings

  _client: httpx.AsyncClient | None = None
  _client_lock = asyncio.Lock()
  _cache: dict[str, tuple[float, Any]] = {}
  _cache_lock = asyncio.Lock()

  async def _get_client() -> httpx.AsyncClient:
      global _client
      if _client is not None:
          return _client
      async with _client_lock:
          if _client is None:
              s = get_settings()
              _client = httpx.AsyncClient(
                  base_url=s.msa_base_url,
                  timeout=s.msa_timeout_seconds,
                  headers={"Accept": "application/json"},
              )
          return _client

  async def close_client() -> None:
      global _client
      if _client is not None:
          await _client.aclose()
          _client = None

  async def _get_cached(path: str) -> Any:
      s = get_settings()
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
          _cache[path] = (now + s.msa_cache_ttl_seconds, payload)
      return payload

  async def locations_for_dc(dc_id: int) -> list[dict[str, Any]]:
      payload = await _get_cached(f"/customerlocation/location/siteuse/primarydcid/{dc_id}")
      if isinstance(payload, dict) and "data" in payload:
          rows = payload["data"]
      elif isinstance(payload, list):
          rows = payload
      else:
          raise ValueError(f"Unexpected response shape from msa for dc {dc_id}: {type(payload)}")
      # Filter: SHIP_TO + active site uses only (plan §5b)
      return [
          r for r in rows
          if r.get("siteUseCode") == "SHIP_TO"
          and r.get("siteUseStatus") == "A"
      ]
  ```

  Projection (drop non-needed fields) happens in the `/api/live/dcs/{dcId}/locations` router, not in `msa_client`. Kept fields per plan §5b:
  `siteUseID, locationNumber, customerId, primaryDcId, siteUseCode, siteUseStatus, primarySalesRepId, salesrepName, creditHold, marketingProgAtd, marketingProgVendor`.

### Existing tables/routes touched earlier in the session (not part of live-flow scope)

These already shipped; the next session does not need to revisit them, but should know they exist:

- `backend/app/models/domain.py` — `Market.is_active`, `Dataset.deleted_at` columns.
- `backend/alembic/versions/0002_market_is_active.py`, `0003_dataset_deleted_at.py` — migrations applied.
- `backend/app/api/markets.py` — POST/DELETE with soft delete + name-collision reactivation.
- `backend/app/api/datasets.py` — DELETE soft-delete + list filter on `deleted_at IS NULL`.
- `frontend/src/app/app.{component.ts,html,scss}` — shell with icon rail.
- `frontend/src/app/features/home/home-page/*` — dashboard.
- `frontend/src/app/features/admin/admin-markets-page/*` — market CRUD.
- `frontend/src/app/features/markets/market-picker-page/*` — dataset cards with inline remove.

## 4. Problem Solving

> [!done] Completed (earlier in session, before the live-flow pivot)
> - Frontend refactor end-to-end to atd-angular standards: design tokens, folder-per-component, atd- prefix, NgRx markets/datasets/territory stores, 4 split map sub-components, lazy routes. `npm run build` passes.
> - Soft delete for markets (`is_active`) and datasets (`deleted_at`) — migrations applied via `alembic upgrade head`.
> - Persistent left icon rail in `app.component.*` with hover-expand and active-route stripe.
> - Dashboard page at `/home`.
> - Bug: sidebar contents overflowed 320 px → fixed by global `input, select { width: 100%; min-width: 0 }` + `minmax(0, 1fr)` grid columns. Documented at `frontend/src/styles.scss`.
> - Bug: rail nav items stretched vertically → fixed by switching `.rail__items` from `display: grid` to `display: flex; flex-direction: column; align-self: start` in `app.component.scss`.

> [!warning] Known Issues
> - **`dc_oracle.py` column-name assumptions unverified** — code assumes lowercase `region`, `market`, `dc_name` in `APPS.XXATDAR_DC_REG_MKT_TBL`. Real schema may differ. Confirm before wiring `/api/live/*` routes.
> - **`msa_client.py` was rejected mid-write** — file does not exist on disk; re-create from the snippet above.
> - **Metrics endpoint path unknown** — Phase 2 cannot start until provided. Fields are known (plan §5a).
> - **Sellers endpoint path unknown** — Phase 2 / 3 blocker.
> - **Join key between `/siteuse` and metrics is ambiguous** — `location_cd` may or may not equal `locationNumber`. Confirm with one sample pair from each endpoint.

> [!todo] Remaining Work — Phase 1 of the live-flow plan
> - [ ] **Get plan approval** — user has not yet replied `approve plan` after the latest edits (§5a metrics fields, §7a tables, §10a change-tracking, §10b dynamic filters). Re-confirm scope.
> - [ ] Re-create `backend/app/services/msa_client.py` from snippet in §3 above.
> - [ ] Verify `oracledb` install: `cd backend && uv sync` (or `uv add oracledb`).
> - [ ] Confirm column names in `APPS.XXATDAR_DC_REG_MKT_TBL` with user. Update `dc_oracle.py` if needed.
> - [ ] **Task #13** Create `backend/app/api/live.py` with 4 routes (`/api/live/regions`, `/api/live/markets`, `/api/live/dcs`, `/api/live/dcs/{dcId}/locations`). Wire into `app/api/router.py`. Handle `OracleNotConfiguredError` → 503; handle `httpx.HTTPError` → 502.
> - [ ] Add app shutdown hook to call `dc_oracle.close_pool()` + `msa_client.close_client()`.
> - [ ] **Task #14** Create `frontend/src/app/core/api/live-api.service.ts` with 4 methods.
> - [ ] **Task #14** Create `frontend/src/app/store/live/` NgRx feature: actions, reducer, effects (cascading auto-fetch on region/market change), selectors.
> - [ ] Wire `liveFeature.reducer` + `LiveEffects` into `frontend/src/app/app.config.ts`.
> - [ ] **Task #15** Create `frontend/src/app/features/live/live-dc-picker-page/` (cascading region → market dropdowns + DC list cards).
> - [ ] **Task #15** Create `frontend/src/app/features/live/live-locations-page/` (table with sortable columns; status badge column placeholder; dynamic filter sidebar reading schema endpoint when Phase 2 ships).
> - [ ] Add lazy routes `/live/dcs` and `/live/dcs/:dcId/locations` in `frontend/src/app/app.routes.ts`.
> - [ ] **Task #16** Add a "Live mapping" rail item in `frontend/src/app/app.component.html` between Markets and the Admin section label. Use a distinct icon (suggest database / satellite SVG).
> - [ ] **Task #17** `cd frontend && npm run build`. `cd backend && uv run ruff check && uv run python -m compileall app`.
> - [ ] (Phase 2 prep) Once user provides metrics URL, add `app/services/msa_client.py:metrics_for_location(siteUseID)` + `/api/live/locations/{siteUseID}/metrics` route. Map fields per plan §5a. Surface lat/lng on a future map page.
> - [ ] (Phase 3 prep) Create alembic `0004_live_assignments.py` for `location_assignments` + `location_assignment_events` tables when Phase 3 begins.

Tasks in the live session task list (currently pending — re-use these IDs or recreate):

```
#11 Backend: Oracle DC service + config            (mostly done — see §3)
#12 Backend: prod-msa proxy client                 (file lost, re-do)
#13 Backend: /api/live/* routes                    (not started)
#14 Frontend: live store + API                     (not started)
#15 Frontend: DC picker + locations table pages    (not started)
#16 Nav rail: add Live mapping section             (not started)
#17 Build verify                                   (not started)
```

## 5. Current Work

Immediately before the handoff request, the user provided the **metrics API field list**:

```
customer_cd, location_cd, dba_name, address, city_name, state_cd,
county_name, zip_cd, latitude, longitude, delivery_tier, tire_pros,
customer_group_name, customer_class_name, customer_channel_name,
mtdsales, ytdsales, mtdunits, ytdunits, priorytdsales
```

This was added to `plan-live.md` as a new **§5a — Metrics API — confirmed field set** with inferred type mappings (toggle / range / multiselect / text) per the §10b auto-filter rules, plus three implications:

1. Join key between `/siteuse` and metrics is ambiguous — confirm before Phase 2.
2. Lat/lng come from metrics, not `/siteuse` — map page blocked on metrics endpoint.
3. Currency formatting needed for `mtdsales`, `ytdsales`, `priorytdsales`.

Also flagged a derived metric for later: `ytdDeltaPct = (ytdsales − priorytdsales) / priorytdsales`.

The plan still needs the user's `approve plan` reply before Phase 1 coding begins.

## 6. Next Step

**Re-confirm plan approval, then start Phase 1.** Concretely:

1. Ask the user: "Plan is now at `plan-live.md` with §3, §5, §5a, §6, §7, §7a, §8, §9, §10a, §10b. Approve to start Phase 1?"
2. If approved, work through the todo list in §4 above in order (msa_client recreate → oracledb install → live router → frontend store → pages → nav rail → build verify).
3. Phase 1 explicitly **does not** include the map, metrics endpoint, or assignment persistence — those are Phase 2 and Phase 3 in `plan-live.md` §10.

Do not start Phase 2 work until the user provides the metrics endpoint URL.
