# Plan — Live API-driven Territory Mapping

Author: Claude · Draft: 2026-05-20 · Status: **Phase 1 + 2a + 2b + 3a + 3b + 3c.1 + 3c.2 + 3c.3 shipped. Editorial-terminal UI redesign across all live pages applied (DC picker, locations, map, changes). Remaining: 3c.4 per-row 409 detail, 2b.4 seller-candidate panel (blocked), backfill of legacy region/market/dc_name on existing assignment rows.**

## 1. Goal

Replace the Excel-import flow with a **live, API-driven** flow so the sales-ops user does not need to upload a spreadsheet. Source data is pulled on demand from:

1. **Oracle** — DC / market / region mapping table `APPS.XXATDAR_DC_REG_MKT_TBL`.
2. **prod-msa REST** — `https://prod-msa.gcp.atd-us.com/customerlocation/...` for locations under a DC plus per-location detail and metrics.

The user picks a region → market → DC, sees all locations under that DC enriched with metrics + lat/lng, filters across business fields, picks one or many locations, and assigns a new seller. Saves persist locally in Postgres (audit log). The existing Excel flow stays as a fallback.

## 2. Resolved decisions (from Q&A)

| Question | Decision |
|---|---|
| Metrics + lat/lng source | **Phase 2 POC**: BigQuery direct (`atd-cdp-prod`). **Future**: API call against the same dataset (interface kept stable). |
| BigQuery auth | **Local dev**: ADC (`gcloud auth application-default login`). Service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS` when containerised. |
| BQ → /siteuse join key | `location_cd` (BQ) == `locationNumber` (/siteuse). Batched: one BQ query per DC fetch, `IN UNNEST(@location_cds)`. |
| Seller list source | prod-msa REST, called per location (path TBD — single-location detail endpoint returns many fields including seller candidates) |
| Auth to prod-msa | **None** — internal network |
| Where assignments persist | Local Postgres only (audit log). No write-back to source. |
| Keep Excel flow? | Yes — keep as fallback |
| Phase 1 scope | **DC picker + locations table only.** No map yet. |
| Assignment key | `siteUseID` |
| DC picker UX | Cascading: region → market → DC list |

## 3. Open items

**Resolved 2026-05-20**

1. ~~Metrics endpoint path~~ — replaced for POC by **BigQuery direct** against `atd-cdp-prod.edw.dim_customer_location` + `edw.dim_customer` + `dbt.stg_crm_account_sales`. Eventually a metrics API will wrap this query; `bq_metrics.metrics_for_locations(...)` is the stable interface — swap the implementation without touching the router.
2. ~~Lat/lng field names~~ — `latitude`, `longitude` on `dim_customer_location`.
3. ~~Lat/lng nulls in BQ~~ — handled by **Postgres geocode cache + Census batch geocoder fallback**. `lat_source` on every row tells UI whether the coord is from BQ (`source`) or Census (`census`) or missing (`null`). State-mismatch reject guards against pin-on-wrong-coast bugs.
4. ~~Column names in `APPS.XXATDAR_DC_REG_MKT_TBL`~~ — verified live (it's a synonym for `XXATDAR.XXATDAR_DC_REG_MKT_TBL`). Real columns: `REGION_NAME`, `MARKET`, `DC_NAME`, `DC_NO` (3-char text), `ORGANIZATION_ID` (numeric, matches `primaryDcId` in /siteuse), `DISABLE_DATE` (soft delete), `OPERATING_UNIT` (filter = 82 for US).

**Still open**

5. **Single-location detail endpoint path** — exact URL + sample JSON. Holds seller-candidate fields. Blocks Phase 2b.4 seller-candidate panel.
6. **Seller list source for Phase 3 assignment UI** — three options: (a) free-text typed by user, (b) distinct `salesrepName`/`primarySalesRepId` already in /siteuse for the DC, (c) wait for (5). Recommend (b) until (5) lands.
7. **Oracle credentials** — user / password / DSN that the FastAPI process will use. Env vars only; will not be committed.
8. **Expected DC sizes** — typical location count per DC drives whether the all-locations BQ batch is fine forever or needs paging. Current implementation batches all `location_cd` values for the DC into one `IN UNNEST` call.
9. **Caching policy** — current defaults: 5 min for /siteuse (`MSA_CACHE_TTL_SECONDS=300`) and 5 min for BQ metrics per DC (`BQ_METRICS_CACHE_TTL_SECONDS=300`). Geocode cache is permanent (no TTL). Adjust if metrics need to be fresher than 5 min.

## 4. Architecture additions

```
                                ┌─────────────────────────┐
  Angular SPA  ─── /api/live ───┤   FastAPI (existing)    │
                                │                         │
                                │  app/api/live.py        │── oracledb pool ──▶ Oracle (APPS.XXATDAR_DC_REG_MKT_TBL)
                                │  app/services/          │
                                │    dc_oracle.py         │── httpx client  ──▶ prod-msa.gcp.atd-us.com (/siteuse)
                                │    msa_client.py        │
                                │    bq_metrics.py        │── google-cloud-bigquery ──▶ BigQuery (atd-cdp-prod)
                                │    geocode_enrich.py    │── geocoder.py    ──▶ geocoding.geo.census.gov (fallback)
                                │                         │     + Postgres geocode_cache (caches hits + misses)
                                │    filter_schema.py     │── infer descriptors from merged payload (§10b)
                                │    live_assign.py       │── SQLAlchemy ────▶ Postgres location_assignments
                                │                         │                  + location_assignment_events
                                │                         │   (PATCH/DELETE single, POST bulk + bulk-revert,
                                │                         │    POST reconfirm, GET /changes, GET /changes/summary,
                                │                         │    GET /changes.csv stream)
                                └─────────────────────────┘
```

**New backend dependencies**
- `oracledb` (async, thin-mode — no Oracle client needed).
- `httpx` (already present) — shared `AsyncClient` for prod-msa.
- `google-cloud-bigquery` — Phase 2 metrics source. Sync client wrapped via `asyncio.to_thread`. ADC for local, service-account JSON for containers.
- *(reused)* `CensusBatchGeocoder` from the Excel flow for Phase 2b geocode fallback.

**Backend config additions** (`app/core/config.py`)
- `oracle_user`, `oracle_password`, `oracle_dsn`, `oracle_pool_min`, `oracle_pool_max`
- `msa_base_url`, `msa_timeout_seconds`, `msa_cache_ttl_seconds`
- `bigquery_project` (default `"atd-cdp-prod"`), `bq_metrics_cache_ttl_seconds` (default 300)
- *(reused)* `census_batch_url`, `geocode_chunk_size`

**New database tables (Phase 2b)**
- `geocode_cache(address_key UNIQUE, street, city, state, zip, latitude, longitude, matched, matched_address, source, created_at)` — Postgres cache for Census fallback. Stores misses (`matched=false`) too, preventing repeated Census calls for unmatchable addresses.

**New database tables (Phase 3a)**
- `location_assignments(id UUIDv7, site_use_id UNIQUE, location_number, customer_id, dc_id, market, region, dc_name, previous_seller_id/name, current_seller_id/name, assignment_changed, assigned_by, assigned_at, version, created_at, updated_at)` — current-state per site_use_id. Indexes on `dc_id` + `market`. `dc_name` added by alembic `0006_location_assignment_dc_name` (2026-05-20) so the cross-DC `/live/changes` page can show human DC names without joining Oracle on read.
- `location_assignment_events(id UUIDv7, site_use_id, old/new seller_id+name, changed_by, changed_at, change_source CHECK IN ('single','bulk','revert','reconfirm','import'), assignment_version)` — audit trail. The `reconfirm` source is now actually emitted (3c.1).

**Frontend additions (Phase 2b)**
- Routes: `/live/dcs/:dcId/map` (lazy).
- Components: `LiveMapPageComponent` (maplibre-gl, circle layer, click-to-detail panel, source/census color split, count badges); `LiveFilterSidebarComponent` (standalone, collapsible, sticky, hosts all §10b control types).
- Store additions: `filterSchema`, `activeFilters`, `selectFilteredLocations` selector. `loadFilterSchema` effect auto-fires after `loadLocations`.
- Model additions: `LiveLocation.lat_source`, `FilterDescriptor`, `FilterControl`, `ActiveFilters`.

**Frontend additions (Phase 3a + 3b)**
- Routes: `/live/changes` (lazy) — cross-DC review page.
- Components: `LiveAssignPanelComponent` (single-row side panel, seller picker, Save / Accept-source), `LiveChangesPageComponent` (cross-DC table + filters + bulk revert).
- Locations page: Status badge column, Assigned column, status filter chips, row-click side panel, **checkbox multi-select + sticky bulk-bar**, **client-side pagination** (25/50/100/250 rows).
- Map page: **rectangle-select toggle** (drag-to-select multiple pins) + **seller-color pins** with a legend panel (top 12 sellers + count + "+N more"); divergence hint when filter-by-live differs from assigned. Bulk-bar above map with seller picker + Apply.
- Nav rail: "Changes" entry under "Live mapping".
- Store additions: `statusFilter`, `saving`, `saveMessage`; actions `saveAssignment*`, `revertAssignment*`, `setStatusFilter`; selectors `selectStatusCounts`, `selectFilteredLocations` now also applies status chip filter.
- Model additions: `AssignmentBlock`, `AssignmentStatus`, `AssignmentPatchInput`, `ChangeRow`, `ChangesPage`, `ChangesSummary`, `BulkAssignInput`.

**Lifecycle**
- Oracle pool: lazy init on first request; closed on app shutdown.
- httpx client: lazy init; closed on shutdown.

## 5. New API surface — Phase 1

All under `/api/live`. All require authenticated user (or local-dev bypass).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/live/regions` | Distinct regions from Oracle |
| GET | `/api/live/markets?region=…` | Distinct markets, optionally filtered by region |
| GET | `/api/live/dcs?region=…&market=…` | DC rows from Oracle |
| GET | `/api/live/dcs/{dcId}/locations` | Proxy `…/siteuse/primarydcid/{dcId}` — list shape unchanged |

Errors:
- `503` with `{detail: "Live endpoints disabled — Oracle not configured."}` when env vars missing.
- `502` for upstream prod-msa failures, body includes upstream status.

## 5b. Locations API — filter + projection

The proxy for `/customerlocation/location/siteuse/primarydcid/{dcId}` must **filter** and **project** the upstream payload before returning to the UI.

### Filter

Keep only rows where **both** conditions hold:

- `siteUseCode == "SHIP_TO"` — upstream returns multiple site-use codes per customer (BILL_TO, SHIP_TO, etc.); only ship-to locations are in scope for territory mapping.
- `siteUseStatus == "A"` — exclude inactive / closed site uses.

```python
# in msa_client.py, after fetch
rows = [
    r for r in raw
    if r.get("siteUseCode") == "SHIP_TO"
    and r.get("siteUseStatus") == "A"
]
```

### Projection (returned fields)

Keep these fields per location and drop the rest. The shape the backend returns to the UI:

```jsonc
{
  // identity
  "siteUseID": "3479",
  "locationNumber": "2605",
  "customerId": 2195,
  "primaryDcId": 102,
  "siteUseCode": "SHIP_TO",        // always SHIP_TO after filter; kept for explicitness
  "siteUseStatus": "A",            // always "A" after filter; kept for explicitness

  // live seller (drives status derivation in §10a)
  "primarySalesRepId": 100669457,
  "salesrepName": "HUGGINS, CHARLES",

  // business / risk signals
  "creditHold": null,              // null | "Y" | "N" — boolean-ish; auto-filter renders as toggle
  "marketingProgAtd": null,        // delimited string or null — auto-filter renders as multiselect-of-tokens (see below)
  "marketingProgVendor": "FALKEN_SECONDARY*HANKOOK_ONE*HERCULES_OPENMKT*..."
}
```

### Multi-value string fields

`marketingProgAtd` and `marketingProgVendor` are delimited (`*` separator in the sample). Treat them as **multi-value** for filtering:

- Split on `*` when computing the filter schema.
- Auto-filter control: **multiselect-with-tokens**. User picks one or more programs; row matches if ANY of its tokens intersect the selected set.
- Plan §10b's inference rules will need a small tweak to detect `*`-delimited strings → multi-value multiselect.

### Combined view with metrics (Phase 2)

Phase 1 returns just the projected `/siteuse` fields above. Phase 2 will merge each row with the metrics payload (plan §5a) on `siteUseID` (or `location_cd` if that's the actual join key — to be confirmed). The merged row will be what feeds the locations table.

### Update to §5 endpoint contract

`GET /api/live/dcs/{dcId}/locations` response is now the projected + filtered list described above. The handler will:

1. `await msa_client.locations_for_dc(dc_id)` → raw payload.
2. Filter `siteUseCode == "SHIP_TO"` **and** `siteUseStatus == "A"`.
3. Project to the field set above.
4. (Phase 3) Left-join with `location_assignments` on `siteUseID` and attach the `assignment` block from §10a.

## 5a. Metrics API — confirmed field set

Path still TBD, but the **fields** the metrics endpoint will return are confirmed:

| Field | Likely type (inferred) | Notes |
|---|---|---|
| `customer_cd` | string | Customer code. Join key candidate. |
| `location_cd` | string | Same as `locationNumber` from /siteuse? Confirm. |
| `dba_name` | string | "Doing business as" — display label. |
| `address` | string | Street address. |
| `city_name` | string | |
| `state_cd` | string | 2-letter state. |
| `county_name` | string | |
| `zip_cd` | string | |
| `latitude` | number | **Drives map pin position.** |
| `longitude` | number | **Drives map pin position.** |
| `delivery_tier` | string (low-cardinality → multiselect) | |
| `tire_pros` | boolean (Y/N) | Toggle filter. |
| `customer_group_name` | string (low-card → multiselect) | |
| `customer_class_name` | string (low-card → multiselect) | |
| `customer_channel_name` | string (low-card → multiselect) | |
| `mtdsales` | number | Range filter. Currency. |
| `ytdsales` | number | Range filter. Currency. |
| `mtdunits` | number | Range filter. |
| `ytdunits` | number | Range filter. |
| `priorytdsales` | number | Range filter. Currency. **Useful for YoY delta.** |

### Implications

- **Join key** between `/siteuse/primarydcid/{dcId}` (returns `siteUseID`, `locationNumber`, `customerId`) and metrics (returns `customer_cd`, `location_cd`) is **not yet definitive**.
  - If `location_cd` == `locationNumber`, that's the join.
  - If `customer_cd` is the Oracle account/customer code matching `customerId`, we may need both keys.
  - **Action**: confirm the exact join condition with one sample pair from each endpoint before Phase 2 coding.
- **Lat/lng come from metrics, not /siteuse** — so the map page cannot render until metrics endpoint is live. Phase 1 (locations table) does not need lat/lng → can ship without metrics.
- **Phase 1 column hint**: even before metrics endpoint exists, we can leave column slots for these fields and show "—" placeholders.
- **Currency formatting**: sales fields should render with `$` + locale grouping. Filter ranges respect raw numeric values.
- **Auto-filter behavior** (per §10b): on first metrics fetch the schema endpoint will surface ranges for the 5 numeric fields, multiselects for the low-cardinality string fields, and a toggle for `tire_pros` — no code change required.

### Derived metrics worth computing client-side

- `ytdDeltaPct = (ytdsales − priorytdsales) / priorytdsales` — surfaces decline accounts. Could become a filter once we add a "computed fields" layer (out of scope Phase 1).
- `avgUnitPrice = ytdsales / ytdunits` (guard div-by-zero).

## 6. New API surface — Phase 2

**Shipped (read):**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/live/dcs/{dcId}/locations?withMetrics=true&geocodeFill=true&withAssignments=true` | /siteuse projection LEFT-JOIN BQ metrics on `location_cd == locationNumber` + Postgres `geocode_cache` + Census fallback + assignment block + derived `status`. `lat_source` + `assignment.status` on every row. 5-min TTL per DC. |
| GET | `/api/live/dcs/{dcId}/filter-schema` | Auto-inferred filter descriptors for the merged payload (§10b). |

**Shipped (write — Phase 3):**

| Method | Path | Purpose |
|---|---|---|
| PATCH  | `/api/live/locations/{siteUseID}/assignment` | Single seller assignment. Body `{sellerId, sellerName, liveSellerId, liveSellerName, expectedVersion, ...}`. 409 on version mismatch. |
| DELETE | `/api/live/locations/{siteUseID}/assignment` | Accept-source. Body `{expectedVersion}`. Writes `change_source='revert'` event. |
| POST   | `/api/live/assignments/bulk` | All-or-nothing batch: one seller for many siteUseIDs. Per-row `change_source='bulk'` events. |
| POST   | `/api/live/changes/bulk-revert` | All-or-nothing batch Accept-source. |
| GET    | `/api/live/changes` | Paginated list of `location_assignments` rows. Filters: region/market/dcId/assignedBy/currentSellerId/onlyChanged. |
| GET    | `/api/live/changes/summary` | `{total, changed, byRegion, byDc}` for dashboard tile + header counters. |

**Deferred until URLs known:**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/live/locations/{siteUseID}` | Single-location detail proxy (seller candidates, business fields) |

**Performance choice — why bulk-via-BQ instead of fan-out HTTP**

- Original plan was per-location HTTP calls with `asyncio.Semaphore(20)` + per-location TTL cache.
- BQ approach replaces N HTTP calls with **one parameterized query** for the whole DC. Latency drops from O(N × p99 HTTP) to O(1 BQ job).
- BQ client is sync → wrapped via `asyncio.to_thread` so it doesn't block the event loop.
- Future swap: when the metrics API ships, replace `bq_metrics.metrics_for_locations` with an HTTP call against the same shape. Router and frontend stay unchanged.

**When this breaks**: DCs returning > a few thousand locations — `IN UNNEST` has a parameter-size limit. If a DC is huge, split into chunks of 1000 and merge. Not implemented yet because expected DC sizes are still open (§3 item 6).

## 7. New API surface — Phase 3 (assignment persistence)

| Method | Path | Purpose |
|---|---|---|
| PATCH | `/api/live/locations/{siteUseID}/assignment` | Single seller assignment |
| POST | `/api/live/assignments/bulk` | All-or-nothing batch |

## 7a. Existing tables — relevance to live flow

The live flow does **not** reuse the Excel-era domain tables. They remain valid for the Excel fallback only.

| Table | Used by Excel | Used by Live | Notes |
|---|---|---|---|
| `users` | yes | **yes** | Shared identity. Both flows record `assigned_by` referencing users. |
| `markets` | yes | no | Local rows created during Excel import. Live flow uses market *strings* from Oracle — no FK. |
| `user_market_access` | yes | partial | Keyed by local `market_id`. For live access control, we'll either re-use it by mapping Oracle market name → local market row, or introduce a `user_live_market_access(user_id, region, market)` table. Phase 3 decision. |
| `datasets` | yes | no | Excel-only. |
| `accounts` | yes | no | Excel-only. Live flow does **not** persist locations as rows. |
| `sellers` | yes | no | Excel-only normalised seller list. Live seller candidates come from prod-msa. |
| `assignment_events` | yes | no | FK to `accounts.id`. Live flow has its own audit table (§8). |
| `import_jobs` | yes | no | Excel-only. |

**If the Excel flow is later retired**, the following can be dropped:
`markets`, `user_market_access`, `datasets`, `accounts`, `sellers`, `assignment_events`, `import_jobs`. The `postgis` extension also becomes optional (live flow has lat/lng but doesn't query geometry server-side).

## 8. New database tables

**`location_assignments`** — current state per location.

```
id                  UUID v7 PK
site_use_id         text UNIQUE NOT NULL
location_number     text
customer_id         bigint
dc_id               integer
market              text
region              text
previous_seller_id  bigint
previous_seller_name text
current_seller_id   bigint
current_seller_name text
assignment_changed  boolean NOT NULL DEFAULT false
assigned_by         text
assigned_at         timestamptz
version             integer NOT NULL DEFAULT 0
created_at          timestamptz NOT NULL DEFAULT now()
updated_at          timestamptz NOT NULL DEFAULT now()
```

**`location_assignment_events`** — audit history.

```
id                  UUID v7 PK
site_use_id         text NOT NULL  (FK to location_assignments)
old_seller_id       bigint
new_seller_id       bigint
old_seller_name     text
new_seller_name     text
changed_by          text NOT NULL
changed_at          timestamptz NOT NULL DEFAULT now()
change_source       text NOT NULL CHECK (change_source IN ('single','bulk'))
assignment_version  integer NOT NULL
```

Indexes:
- `location_assignments(dc_id)`
- `location_assignments(market)`
- `location_assignment_events(site_use_id)`

Migration: `0004_live_assignments.py` (created during Phase 3, not Phase 1).

## 9. Frontend additions

**State (NgRx)** — new feature `store/live/`:
- `regions`: string[]
- `markets`: string[]   (filtered by selected region)
- `dcs`: DC[]            (filtered by selected region + market)
- `selectedRegion`, `selectedMarket`, `selectedDcId`
- `locations`: Location[]  (raw payload from /siteuse)
- `loading`, `error`

Actions: `LoadRegions`, `RegionSelected`, `MarketSelected`, `LoadDcs`, `LoadLocations`, plus *Success/Failure pairs.

Effects: cascading auto-fetch — selecting region triggers markets load; selecting market triggers DC load; DC click triggers locations load.

**API service** — `core/api/live-api.service.ts`:
- `regions()`, `markets(region?)`, `dcs(region?, market?)`, `locationsForDc(dcId)`.

**Routes / pages**
- `/live` → redirect to `/live/dcs`
- `/live/dcs` → `LiveDcPickerPageComponent` (cascading dropdowns + DC list cards)
- `/live/dcs/:dcId/locations` → `LiveLocationsPageComponent` (sortable/filterable table)

**Nav rail**
- Add a "Live mapping" section above the Admin section with one rail item linking to `/live/dcs`. Use a different icon (e.g. database / satellite) to distinguish from Excel-driven Markets.

## 10. Phase plan

| Phase | Deliverable | Status |
|---|---|---|
| **1** | Oracle DC service + prod-msa proxy + DC picker + locations table | **Shipped** 2026-05-20 |
| **2a (POC)** | BigQuery metrics merge + extended locations table (DBA, city/state, tier, tire_pros, YTD/MTD$, YoY Δ, class, channel) | **Shipped** 2026-05-20 |
| **2b.1** | Map view (maplibre, lat/lng pins, click → side panel, source/census color split) | **Shipped** 2026-05-20 |
| **2b.2** | Geocode fallback: Postgres `geocode_cache` + Census batch geocoder; `lat_source` provenance returned + visualised | **Shipped** 2026-05-20 |
| **2b.3** | Dynamic filter schema (§10b) — `/api/live/dcs/{dcId}/filter-schema`, sidebar with toggle / range / multiselect / tokens / text, collapse, active-dot, shared across locations + map | **Shipped** 2026-05-20 |
| **2b.4** | Seller-candidate panel (single-location prod-msa detail) | **Blocked** — endpoint URL TBD |
| **3a** | Local assignment persistence (`location_assignments` + `location_assignment_events`), §10a status derivation, single-row PATCH/DELETE, status chips, row-click assign panel | **Shipped** 2026-05-20 |
| **3b** | `/live/changes` global review page + summary; bulk-assign (POST `/assignments/bulk`); bulk-revert (POST `/changes/bulk-revert`); checkbox multi-select on locations + map rectangle-select; sticky bulk-bar on both views; nav rail "Changes" entry | **Shipped** 2026-05-20 |
| **3c.1** | Reconfirm action on stale rows — new `POST /api/live/locations/{site_use_id}/reconfirm` + `live_assign.reconfirm_assignment` (re-anchors `previous_seller_id` to live, bumps version, emits `change_source='reconfirm'` audit event); UI button in `LiveAssignPanelComponent` visible only when `status === 'stale'`. | **Shipped** 2026-05-20 |
| **3c.2** | `/home` dashboard tile — `HomePageComponent` calls `LiveApiService.changesSummary()` via `toSignal` w/ empty-fallback; warning-styled "Live changes" tile + "Live flow" quick-action section linking to `/live/dcs` and `/live/changes`. | **Shipped** 2026-05-20 |
| **3c.3** | CSV export — new `GET /api/live/changes.csv` streams rows via generator + StringIO buffer (cap 100k); UI "Export CSV" button on `/live/changes` triggers download with current filter params. | **Shipped** 2026-05-20 |
| **3c.4** | Per-row 409 detail in bulk endpoints — return `{ok: [...], conflicts: [{siteUseId, expected, actual}]}` so UI can flag which rows lost the race. Bulk-assign + bulk-revert now accept `expectedVersions` map; service collects conflicts instead of raising. UI re-selects conflicting rows + surfaces toast/message. | **Shipped** 2026-05-20 |
| **3d** | DC context on assignment rows — new alembic `0006_location_assignment_dc_name` adds `dc_name`; `upsert_assignment` / `bulk_upsert` accept `dc_name` + backfill missing `dc_id/market/region/dc_name` on update; `/changes` API returns `dcName`; payload sites in frontend (locations + map page) pass `dcName/market/region` via `currentDc` selector. | **Shipped** 2026-05-20 |
| **4** | Polish: seller-color pins + legend + divergence hint; pagination on locations table (25/50/100/250); filtered-count badge on map; clustering for dense DCs; **custom seller-color overrides** (shared via new `seller_colors` table — click legend swatch → native picker; reset via × button); **map clustering** (maplibre native `cluster: true` + accent-tinted cluster circles, mono count labels, click to zoom; toggle button in tools row) | **Partial** — seller color + legend + locations pagination + custom color picker + map clustering shipped 2026-05-20; filtered-count badge pending |
| **4b** | Editorial-terminal UI redesign across `/home` tile, DC picker, locations page (incl. shared filter sidebar), map page, changes page. Single-accent palette, mono-numeric ratios, ratio meter, status pills with dots, sticky table thead, full-viewport layout w/ internal scroll, persistent `::-webkit-scrollbar` styles. `frontend-design` skill now mandatory for further frontend work (added to `CLAUDE.md` + project memory). | **Shipped** 2026-05-20 |
| **5** | (Optional) Map filters parity with Excel flow + extra filter controls | All filter types available across live + excel modes |

## 10a. Change tracking — live vs assigned

Every location row the user sees is the **join of two truths**:

- **Live truth** (prod-msa): `primarySalesRepId`, `salesrepName`. Re-fetched every time.
- **Local truth** (Postgres `location_assignments`): `current_seller_id`, `current_seller_name`, `previous_seller_id`, `previous_seller_name`. Only present for locations the user has touched.

The backend joins them on `siteUseID` and computes a derived **status** per row before returning to the UI.

### Status states

| Status | Condition | UI cue | Meaning |
|---|---|---|---|
| `unchanged` | no row in `location_assignments` for this `siteUseID` | neutral / no badge | We haven't touched this location. Seller is whatever live says. |
| `assigned` | local row exists AND `current_seller_id == live primarySalesRepId` | green dot | We saved an assignment and source already matches — nothing to push, no divergence. |
| `changed` | local row exists AND `current_seller_id != live primarySalesRepId` AND `previous_seller_id == live primarySalesRepId` | blue "Changed" badge | User intentionally moved this location to a new seller. Source still has the old seller. **This is the export queue.** |
| `stale` | local row exists AND `current_seller_id != live primarySalesRepId` AND `previous_seller_id != live primarySalesRepId` | amber "Source updated" warning | Source changed since the user assigned (someone updated the upstream rep). The user needs to decide: keep their assignment, or accept the new source value. |

### Backend response shape (additions)

`GET /api/live/dcs/{dcId}/locations` returns each location with an extra block:

```jsonc
{
  "siteUseID": "3479",
  "locationNumber": "2605",
  "live": {
    "sellerId": 100669457,
    "sellerName": "HUGGINS, CHARLES"
  },
  "assignment": {
    "status": "changed",         // unchanged | assigned | changed | stale
    "sellerId": 100774422,        // null when status == unchanged
    "sellerName": "SMITH, JANE",
    "previousSellerId": 100669457,
    "previousSellerName": "HUGGINS, CHARLES",
    "assignedAt": "2026-05-20T13:20:00Z",
    "assignedBy": "rpogula@atd.com",
    "version": 2
  }
}
```

### UI surfaces

Two surfaces, both shipping in Phase 3:

#### Surface A — inline on each DC's locations page (`/live/dcs/:dcId/locations`)

Used while *doing* assignment work in context.

1. **Locations table** — two seller columns side by side ("Live seller", "Assigned seller") + a status column with the badge. Default sort puts `changed` rows first.
2. **Filter chips** above the table:
   - `All` · `Changed only` · `Stale` · `Assigned (matches source)` · `Unchanged`
   - Header counter: `12 changed · 3 stale · 145 total` (scoped to this DC).
3. **Row / pin detail** — side-by-side card:

   ```
   Live seller             →   Assigned seller
   HUGGINS, CHARLES             SMITH, JANE
   (source of truth)            (assigned 2 days ago by R. Pogula)
   ```
   Plus two buttons:
   - **Accept source** — deletes the local assignment row. Status returns to `unchanged`.
   - **Re-confirm** (only shown for `stale`) — copies the current live seller into `previous_seller_id` and bumps version. Effectively says "yes I still want SMITH, JANE even though upstream changed."

#### Surface B — global change-review page (`/live/changes`)

Used to *review* divergence across the whole organisation. Manager-oriented.

1. **Cross-DC table** — every row in `location_assignments` where status is `changed` or `stale`. Columns: region, market, DC name, location number, customer, live seller, assigned seller, assigned by, assigned at, status badge.
2. **Filter bar** — region multi-select, market multi-select, DC multi-select, status (`changed`/`stale`/`assigned`), seller (assigned), assigned-by user, date range.
3. **Row click** — drills into `/live/dcs/:dcId/locations?focus=:siteUseID` (same inline detail panel pops open, scrolled to that location).
4. **Bulk actions** — `Accept source for selected`, `Re-confirm selected`, `Export CSV` (for downstream consumers).
5. **Dashboard tile** on `/home` — "N locations have pending assignment changes" linking here.

#### Backend endpoints supporting Surface B

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/live/changes` | All assignments where status ∈ {`changed`, `stale`}; supports region/market/dc/seller/assignedBy/from/to filters; paginated |
| GET | `/api/live/changes/summary` | Counts by status, by region, by DC. Powers the dashboard tile + header counters |
| POST | `/api/live/changes/bulk-revert` | All-or-nothing batch of "accept source" actions |
| POST | `/api/live/changes/bulk-reconfirm` | All-or-nothing batch of re-confirm actions |

Implementation note: `/api/live/changes` does **not** call prod-msa for every row in the list — that's an N+1 hazard. Instead it relies on the `previous_seller_id` baseline stored at assignment time vs the most recent live seller observed during the last per-DC fetch (cached). When a user opens a specific row, that single location is refreshed against prod-msa to confirm status.

### Lifecycle rules

- On every **GET /api/live/dcs/{dcId}/locations**: fresh live fetch + join with local rows. Status recomputed every request — never cached past TTL.
- On **PATCH single assignment**: if `new_seller_id == live.sellerId`, we still write the row but with status flipped to `assigned` (so we have a record). If `new_seller_id == previous local current_seller_id`, no-op + 200.
- On **delete local assignment** (Accept source): row removed, audit event written with `change_source = 'revert'`.
- `version` increments on every meaningful change (assign, re-assign, re-confirm). Optimistic-lock check on PATCH unchanged from the Excel flow.

### Audit log additions

`location_assignment_events.change_source` enum gains two values:
- `revert` — user accepted source and cleared the local assignment.
- `reconfirm` — user re-confirmed a stale assignment after source changed.

So the full enum becomes: `single | bulk | revert | reconfirm | import`.

## 10b. Dynamic filter schema

Filters are **not hardcoded**. They are derived from the actual location + metrics payloads returned for the active DC, so any new field upstream-side appears as a filter automatically.

### Inference rules

For each top-level field across the loaded locations:

| Observed shape | Control type | Notes |
|---|---|---|
| `true` / `false` / `"Y"` / `"N"` (case-insensitive) | **toggle** | Two-state: include / exclude. |
| `number` | **range slider with min/max inputs** | Min/max defaults computed from sample. |
| ISO 8601 date or `"YYYY-MM-DD"` | **date range** | From/to pickers. |
| `string` with ≤ 20 distinct values | **multi-select dropdown** | Distinct values shown with count. |
| `string` with > 20 distinct values | **text contains-search** | Case-insensitive. |
| arrays / nested objects | **skipped** | Not filterable in Phase 1. Could expose later via JSONPath. |

Fields excluded by default (avoid noise):
- `id`, `siteUseID`, `customerId`, `siteUseStatus` internals (still visible in detail, just not filter controls)
- lat / lng fields
- raw timestamps that already feed the date-range control

### Endpoint

`GET /api/live/dcs/{dcId}/filter-schema` — returns an array of field descriptors derived from the same locations + metrics payload the table uses. Computed once per DC fetch and cached alongside the locations payload.

```jsonc
[
  {
    "field": "customerCategoryCode",
    "label": "Customer category",
    "control": "multiselect",
    "options": [
      { "value": "WHOLESALE CUSTOMER", "count": 142 },
      { "value": "RETAIL", "count": 18 }
    ]
  },
  {
    "field": "creditCardFlag",
    "label": "Credit card flag",
    "control": "toggle"
  },
  {
    "field": "ttmUnits",
    "label": "TTM units",
    "control": "range",
    "min": 0,
    "max": 48210
  },
  {
    "field": "salesrepName",
    "label": "Salesrep name",
    "control": "text"
  }
]
```

The frontend renders the filter sidebar dynamically by mapping each descriptor to its `*FilterControlComponent`. No code change required to add a new filter when upstream adds a field.

### Filter execution

All filtering happens **client-side**, in NgRx selectors over the in-memory locations array:

- One pull per DC load fetches everything (locations + metrics if Phase 2).
- The `selectFilteredLocations` selector composes: full list → apply each active filter → return view.
- Counts (`12 changed · 3 stale · 145 total`) recompute as derived signals.

This avoids per-keystroke round-trips and works because a DC fits in browser memory (sub-10k rows expected, single-digit MB).

### Persisted filter presets (Phase 3+)

Once Phase 1 ships, optionally allow users to save filter presets to `localStorage` (per DC) or to Postgres as a `user_filter_presets(user_id, dc_id, name, payload_json)` table. Not in current scope; tracked as future work.

### Status filter integration

The four `status` values (`unchanged`/`assigned`/`changed`/`stale`) appear as a **fixed**, always-present filter chip row (§10a) — they're a derived field, not raw payload, so they don't go through the auto-schema path.

## 11. Risks & open questions

1. **N+1 metrics calls** — per-location calls scale poorly. Mitigations: bounded concurrency, TTL cache, lazy on-click pattern. Need real DC size to validate.
2. **Oracle thin-mode driver** — `oracledb` thin works without Oracle Client but requires the DB to accept TLS / native auth modern enough; verify against ATD Oracle version.
3. **prod-msa contract drift** — no schema agreement. Backend should treat fields as optional and not crash if a field disappears.
4. **Soft-delete on live** — no analog yet; we're not storing locations as rows, so nothing to delete locally. Source-of-truth deletion is upstream.
5. **Seller candidate logic** — user mentioned "we already have logic" for picking the right seller. Where does that logic live? Backend rules? Or just a list the user sees and chooses from? Need clarity in Phase 2.
6. **Concurrency on assignments** — same optimistic-lock pattern via `version` column. Carry over from Excel-flow design.
7. **Nav clarity** — two parallel flows (Excel "Markets" + Live "Live mapping") could confuse users. Consider labeling or eventually deprecating Excel mode.

## 12b. Recent additions — 2026-05-20 second pass

### 3c.1 — Reconfirm action

- **Service**: `live_assign.reconfirm_assignment(site_use_id, live_seller_id, live_seller_name, expected_version, changed_by)`. Re-points `previous_seller_id` to the current upstream live seller, keeps `current_seller_id` (the user's local override), bumps `version`, sets `assignment_changed = (current != live)`, writes an event with `change_source='reconfirm'`. After this, status flips `stale → changed`.
- **Endpoint**: `POST /api/live/locations/{site_use_id}/reconfirm` with body `{liveSellerId, liveSellerName, expectedVersion}`. Returns the standard assignment block.
- **Frontend**: NgRx action `LiveActions.reconfirmAssignment` + effect + reducer (`saveMessage: 'Baseline reconfirmed.'`). Button in `LiveAssignPanelComponent` template, visible only when `status === 'stale'`, warning-styled.

### 3c.2 — Home dashboard tile

- `HomePageComponent` fetches `LiveApiService.changesSummary()` once via `toSignal` + `catchError → empty` fallback (home page never breaks if Postgres is down).
- New warning-styled `tile--live` shows `changed` count over `total · review` hint, links to `/live/changes`.
- New "Live flow" quick-action section: "Pick a DC" → `/live/dcs`, "Review changes" → `/live/changes`.

### 3c.3 — CSV export

- **Endpoint**: `GET /api/live/changes.csv` — same filter params as `/changes` minus pagination. Streams via Python generator + reusable `StringIO` buffer (memory flat for ≤100k rows; cap is hardcoded). Response sets `Content-Disposition: attachment; filename="live-changes-<utc>.csv"`.
- Columns: siteUseID, locationNumber, customerId, dcId, dcName, region, market, previous/currentSellerId+Name, assignmentChanged, assignedBy, assignedAt, version.
- **Frontend**: `LiveApiService.changesCsvUrl(params)` builds URL; `LiveChangesPageComponent.exportCsv()` triggers `window.location.href` so the browser auto-downloads with session cookies intact.

### 3d — DC name + backfill

- Alembic `0006_location_assignment_dc_name` adds `dc_name VARCHAR(255)` to `location_assignments`.
- `upsert_assignment` / `bulk_upsert` accept `dc_name` and **backfill missing `dc_id`/`market`/`region`/`dc_name` on the existing-row update path** — so rows written before §3d that have blank region/market fill themselves on next edit. No data migration script needed.
- `/changes` API response now includes `dcName`. UI shows DC name with a faint mono id suffix in the table.
- Frontend payload sites updated (`live-locations-page.applyBulk`, `live-map-page.applyBulk`, `LiveAssignPanelComponent.save`) to look up the selected DC via `selectDcs` and pass `dcName/market/region`.

### 4b — Editorial-terminal UI redesign (2026-05-20)

Direction: **Bloomberg-terminal-meets-editorial** — single royal-blue accent, amber for tension, sharp 1-px borders (no shadows for chrome), monospace numerics throughout, small-caps micro-labels, `color-mix()` for token-derived tints.

Per-page changes:

| Page | Highlights |
|---|---|
| `/home` | Warning-styled "Live changes" tile + Live-flow quick actions. |
| `/live/dcs` (DC picker) | Editorial header w/ filtered-count meter, bottom-bordered selects w/ custom chevron, card grid w/ staggered fade-in entrance (`staggerMs(i)` cap 360 ms), hover wipe accent rail, mono-caps `DC <id>` tag, region pill + market metaline. |
| `/live/dcs/:id/locations` | Full-viewport flex layout, breadcrumb + DC name + DC-tag + region pill + market subline, ghost CTA "Map view →", search-with-glyph, status chips w/ colored dots + `active = dark fill`, sticky blurred bulk-bar w/ pulsing dot, card-wrapped table w/ sticky thead + zebra + selected-row left rule + status pills + `[title]` for ellipsis recovery. |
| `/live/dcs/:id/map` | Same header pattern, rectangle-select promoted to tool-button (dark-on when active), source/census/missing rendered as chip+dot+count, legend gets `backdrop-blur` + eyebrow + hairline divider, divergence hint as amber-rail card, selection marquee = dashed accent. |
| `/live/changes` | Eyebrow + lede + animated **ratio meter** (changed/total + filling bar) replaces two badges, borderless field rail w/ Toggle pill instead of checkbox, card-wrapped table w/ "changed/same" status pills, mono `By`/`At`/`v` columns. Export CSV button alongside Apply. |
| Filter sidebar (shared) | Densified — collapsed filter rows ~30 % shorter, hairline dividers instead of gap, `height: 100%` to fill the grid row. |

Cross-cutting:

- **Full-viewport pattern**: `:host { height: 100%; overflow: hidden }` → `.page { display: flex; flex-direction: column; height: 100%; overflow: hidden }` → `.content { flex: 1; min-height: 0 }`. Grid foot-gun fixed by using `minmax(0, 1fr)` for the table-col row track (default `1fr` resolves to `minmax(auto, 1fr)` which lets content blow past container).
- **Persistent scrollbars** styled via `::-webkit-scrollbar*` + `scrollbar-width: thin` (Firefox) + `scrollbar-gutter: stable`. macOS overlay-scrollbar default was hiding them.
- `frontend-design` skill is now mandatory before any further Angular UI change. Recorded in:
  - Project `CLAUDE.md` top-of-file block.
  - User memory `feedback_use_frontend_design_skill.md` (with reason + how-to-apply, indexed in MEMORY.md).

## 12. Out of scope for now

- Geocoding service (not needed; lat/lng comes from upstream).
- Excel re-import / parent-dataset linkage (untouched).
- Census batch geocoder code (still mounted but unused for live flow).
- MSAL auth (still local-dev bypass).
- Tests (will follow once Phase 1 routes settle).

---

### Approval needed

If this matches your intent, reply **"approve plan"** and I'll start Phase 1 with these tasks:

1. Add `oracledb` dep + Oracle/MSA settings.
2. `app/services/dc_oracle.py` — async pool + queries.
3. `app/services/msa_client.py` — httpx singleton + TTL cache.
4. `app/api/live.py` — 4 endpoints listed in §5.
5. Frontend `store/live/`, `live-api.service.ts`, two pages, route entries, nav rail update.
6. Build verify (ruff + ng build).

Reply with edits/concerns otherwise.
