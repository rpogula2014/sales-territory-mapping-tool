# Live Flow Phase 2 + Phase 3 + Polish

Slug: `phase-2-3-live-flow` · Created: 2026-05-20 · Working dir: `/Users/jaswanthpogula/git/personal/sales-territory-mapping-tool`

## 1. Primary Request and Intent

This session continued the live API-driven territory-mapping flow from a prior handoff (Phase 1 shipped). The user drove the work through a sequence of explicit requests, each completed before moving on:

1. **Fix Oracle column names** in `dc_oracle.py` — verified live via Oracle MCP against `ebsprda`; the table is actually a synonym → `XXATDAR.XXATDAR_DC_REG_MKT_TBL`. Columns: `REGION_NAME`, `MARKET`, `DC_NAME`, `DC_NO`, `ORGANIZATION_ID` (joins to `primaryDcId`), `DISABLE_DATE` (soft-delete), `OPERATING_UNIT` (=82 for US). User edit further added `OPERATING_UNIT = 82` clause.
2. **Phase 2 metrics — BigQuery direct (POC)**. User supplied the BQ SQL. Wired `app/services/bq_metrics.py` + `?withMetrics=true` flag on `/api/live/dcs/{dcId}/locations`. ADC auth. Stable interface preserved for later API swap.
3. **Census geocode fallback** when BQ has null lat/lng. New Postgres table `geocode_cache`, service `geocode_enrich.py`, `lat_source: 'source' | 'census' | null` provenance per row. State-mismatch reject guard.
4. **Visibility** of lat/lng + geo-source in locations table.
5. **§10b dynamic filter sidebar** — `/api/live/dcs/{dcId}/filter-schema` + `LiveFilterSidebarComponent` (toggle / range / multiselect / multiselect-tokens / text). Collapsible per-section; "Collapse all"; active-dot indicator. UI redesigned after user feedback ("doesn't look clean — each filter looks like a CTA").
6. **Phase 3a — single assignment persistence**. Alembic `0005_live_assignments` + two tables. Status derivation `unchanged | assigned | changed | stale` (§10a). `PATCH/DELETE /api/live/locations/{siteUseID}/assignment`. `LiveAssignPanelComponent` side panel with seller picker, Save, Accept-source.
7. **Phase 3b — global review + bulk**. `/api/live/changes` + `/changes/summary` + `/assignments/bulk` + `/changes/bulk-revert`. New `/live/changes` page. Checkbox column + sticky bulk-bar on locations page.
8. **Map rectangle select** (user pointed out feature gap vs Excel flow) — toggle button, drag-box, individual click toggle, bulk-bar over map.
9. **Color pins by seller** with legend. User then flagged a divergence (filter on live seller, legend showed effective seller) — user picked (c) "keep current + add divergence hint" → added.
10. **Pagination** on locations table; redesigned position when user said "doesn't look professional" (moved into table column, card-styled toolbar).
11. **plan-live.md** updated three times across the session.

## 2. Key Technical Concepts

- **FastAPI + SQLAlchemy async + Alembic** backend.
- **Angular 20** standalone components, NgRx (store/effects/devtools), OnPush, signals, lazy `loadComponent` routes, `inject()` DI, `effect()` + `toSignal()`.
- **atd-angular** standards: folder-per-component, `atd-` prefix, external html/scss, modern control flow (`@if`/`@for`/`@switch`/`@case`).
- **oracledb** async (verified via Oracle MCP `ebsprda` connection).
- **google-cloud-bigquery** with ADC; sync client wrapped via `asyncio.to_thread`. `IN UNNEST(@location_cds)` batch.
- **maplibre-gl** (Phase 2b.1) — single GeoJSON source + circle layer; paint expressions `['case', ['get', 'selected'], ...]` + `['match', ['get', 'lat_source'], ...]` + `['get', 'color']`.
- **Rectangle select** via `boxZoom: false`, mousedown/move/up handlers, `queryRenderedFeatures([start, end])`.
- **Status derivation** (§10a): four states from join of live `primarySalesRepId` × local `(current, previous) seller_id`.
- **Optimistic locking** via `version` column on `location_assignments`; 409 on mismatch.
- **UUID v7** primary keys (`new_uuid7`).
- **CensusBatchGeocoder** reused from Excel flow; `geocode_cache` stores misses too (`matched=false`) to prevent retry storms.
- **Filter inference rules** (§10b): bool-like → toggle; numeric → range; ≤20 distinct strings → multiselect; `*`-delimited strings → multiselect-tokens; otherwise text. Excludes IDs/lat/lng.
- **Deterministic seller-color palette**: 16-step palette, hashed by sellerId.
- **Client-side pagination**: NgRx holds all rows; component slices `sorted()` by `pageIndex × pageSize`. Effect resets page on filter/sort change with `{allowSignalWrites: true}`.

## 3. Files and Code Sections

### `backend/app/services/dc_oracle.py`

- **Why important**: Verified Oracle column names. User edited to add `OPERATING_UNIT = 82` clause.
- **Changes made**: Use `REGION_NAME`, `MARKET`, `ORGANIZATION_ID AS dc_id`, etc. Filter `DISABLE_DATE IS NULL` + `OPERATING_UNIT = 82`.

### `backend/app/services/bq_metrics.py`

- **Why important**: Phase 2 metrics source. Stable `metrics_for_locations(dc_id, location_cds)` interface so API can swap in later.
- **Changes made**: New file. `google-cloud-bigquery` + ADC. 5-min TTL cache per `dc_id`. Sync client via `asyncio.to_thread`.

### `backend/app/services/geocode_enrich.py`

- **Why important**: Census fallback for missing lat/lng. State-mismatch reject prevents pin-on-wrong-coast.
- **Changes made**: New file. `enrich_locations(rows, db)` flow: tag `lat_source='source'` if BQ has coords → look up cache → batch Census misses → persist (including unmatched). Added structured `logger.info(...)` after user reported "no data in geocode table".

### `backend/app/services/filter_schema.py`

- **Why important**: Phase 2b.3. Infers filter descriptors from merged location payload.
- **Changes made**: New file. Excludes IDs/lat/lng. Tokenizes `*`-separated strings.

### `backend/app/services/live_assign.py`

- **Why important**: Phase 3 persistence. Status derivation + single + bulk write paths + audit events.
- **Code snippet** (status derivation §10a):
  ```python
  def derive_status(live_seller_id, assignment):
      if assignment is None: return "unchanged"
      if assignment.current_seller_id == live_seller_id: return "assigned"
      if assignment.previous_seller_id == live_seller_id: return "changed"
      return "stale"
  ```
- Exports: `assignments_for_site_use_ids`, `to_assignment_block`, `upsert_assignment`, `delete_assignment`, `list_changes`, `changes_summary`, `bulk_upsert`, `bulk_delete`.

### `backend/app/api/live.py`

- **Why important**: All read + write endpoints for live flow.
- **Changes made**: `_fetch_merged_locations()` shared pipeline; new endpoints: `/dcs/{id}/locations` (with `withMetrics`, `geocodeFill`, `withAssignments` flags), `/dcs/{id}/filter-schema`, `PATCH /locations/{site}/assignment`, `DELETE /locations/{site}/assignment`, `GET /changes`, `GET /changes/summary`, `POST /assignments/bulk`, `POST /changes/bulk-revert`.

### `backend/alembic/versions/0004_geocode_cache.py`

- New `geocode_cache` table. Applied.

### `backend/alembic/versions/0005_live_assignments.py`

- New `location_assignments` (unique `site_use_id`, indexes on `dc_id`, `market`) + `location_assignment_events` (CHECK on `change_source IN ('single','bulk','revert','reconfirm','import')`). Applied.

### `backend/app/models/domain.py`

- Added `GeocodeCache`, `LocationAssignment`, `LocationAssignmentEvent` ORM classes. Imports extended with `BigInteger`, `CheckConstraint`.

### `frontend/src/app/core/models/live.model.ts`

- Type surface for the full live flow: `LiveDc`, `LiveLocation` (incl. `lat_source`, `assignment`), `AssignmentBlock`, `AssignmentStatus`, `AssignmentPatchInput`, `FilterDescriptor`, `ActiveFilters`, `ChangeRow`, `ChangesPage`, `ChangesSummary`, `BulkAssignInput`.

### `frontend/src/app/core/api/live-api.service.ts`

- All API methods: `regions`, `markets`, `dcs`, `locationsForDc`, `filterSchema`, `patchAssignment`, `revertAssignment`, `changes`, `changesSummary`, `bulkAssign`, `bulkRevert`.

### `frontend/src/app/store/live/{actions,reducer,effects,filters}.ts`

- NgRx live feature. State slices: regions/markets/dcs/locations/filterSchema/activeFilters/statusFilter/saving/saveMessage.
- Selectors: `selectFilteredLocations` composes activeFilters + statusFilter; `selectStatusCounts`.
- Effects: `loadFilterSchemaOnLocations$` (auto-fetch schema after locations land), `saveAssignment$`, `revertAssignment$`.
- `live.filters.ts`: `applyFilters(rows, filters, schema)` — switch on `desc.control`.

### `frontend/src/app/features/live/`

Components shipped this session:
- `live-dc-picker-page/` (Phase 1 — already shipped, untouched).
- `live-locations-page/` — extended with table columns (Lat/Lng/Geo src/Status/Assigned), status chips, checkbox column, sticky bulk-bar, side-panel slot, **pagination** card.
- `live-map-page/` — maplibre map with seller-color pins, source/census ring, legend panel (top 12 + divergence hint), **rectangle select** + bulk-bar.
- `live-filter-sidebar/` — collapsible §10b sidebar, redesigned after user feedback.
- `live-assign-panel/` — single-row assignment side panel.
- `live-changes-page/` — cross-DC review table + filters + bulk revert (route `/live/changes`).

### `frontend/src/app/app.routes.ts`

- Added lazy routes: `/live`, `/live/dcs`, `/live/dcs/:dcId/locations`, `/live/dcs/:dcId/map`, `/live/changes`.

### `frontend/src/app/app.component.html`

- Nav rail entries: "Live mapping" + "Changes".

### `plan-live.md`

- Updated three times across session. Final status banner: **Phase 1 + 2a + 2b + 3a + 3b shipped**. Phase table breaks down: 2b.1 map, 2b.2 geocode fallback, 2b.3 filters, 2b.4 seller-candidate (blocked), 3a single, 3b bulk + changes, 3c pending (reconfirm + home tile + CSV), 4 polish (partial — seller color + pagination shipped). API surface table split into Shipped (read), Shipped (write), Deferred. Architecture diagram now shows `live_assign.py` + Postgres tables.

## 4. Problem Solving

> [!done] Completed
> - Oracle column-name unknowns resolved live via `mcp__oracle__run-sql` against `ebsprda`. APPS.* is a synonym → real owner `XXATDAR`.
> - BQ direct query established as Phase 2 POC source. `bq_metrics.metrics_for_locations` is the swap point when a metrics API ships later.
> - Census-fallback empty-cache mystery: added INFO logging + added Lat/Lng/Geo-src columns to the table for visibility. Likely cause is BQ rows missing both coords AND address (skipped by enrich).
> - User-reported "filter section doesn't look clean" → redesigned sidebar from boxed CTAs to bare collapsible rows with active-dot.
> - Empty-space-on-right (panel column reserved) → toggled `.content--with-panel` class only when a row is selected.
> - Status-chip filter integrated into `selectFilteredLocations`.
> - Map "not working" — diagnosed as legend coloring by effective (assigned) seller while filter is by live seller. User picked option (c): hint banner in legend.
> - Pagination position "didn't look professional" → moved into table column with card-style toolbar.

> [!warning] Known Issues
> - **Phase 2b.4 blocked**: prod-msa single-location detail endpoint URL still unknown — needed for seller-candidate auto-suggest panel.
> - **House Account rows** often lack lat/lng in BQ → don't appear on map. Data-quality problem upstream, not a bug. Visible via the "missing lat/lng" header badge.
> - **Bulk-assign 409 UX**: backend treats the whole batch as all-or-nothing; on a version mismatch the entire call fails and the caller doesn't get row-level detail.
> - **Map `fitBounds`** runs only when `bulkSelected.size === 0`. Doesn't re-fit when filters change with rows selected — minor UX gap.
> - **`uv sync` side effect** earlier in session dropped `ruff` + `pytest` from active env (they live in `[project.optional-dependencies] dev`). Run `uv sync --extra dev` to restore.
> - **`logger.exception` on Census** added but not yet observed in logs since the test DC seemingly had no eligible rows.

> [!todo] Remaining Work
> - [ ] Phase 3c-1: Reconfirm button on `stale` rows in `LiveAssignPanelComponent`. Backend already accepts `change_source='reconfirm'`; just needs a button that re-points `previous_seller_id` at current live seller and bumps version.
> - [ ] Phase 3c-2: `/home` dashboard tile linking to `/live/changes` using `changesSummary()` (counts).
> - [ ] Phase 3c-3: CSV export of `/api/live/changes` (server-side streaming or client-side from the loaded page).
> - [ ] Phase 3c-4: Per-row 409 detail in bulk endpoints — return `{ok: [...], conflicts: [{siteUseId, expected, actual}]}` so UI can flag which rows lost the race.
> - [ ] Phase 2b.4: Seller-candidate panel — wait for prod-msa single-location endpoint URL, then ~30 min of work.
> - [ ] Polish: Map `fitBounds` re-fires when filters change. Map filtered-count badge in header. Marker clustering for dense DCs.
> - [ ] Tests for `live_assign` (upsert / status derivation / bulk logic). Plan §12 deferred this.
> - [ ] `README.md` + `.env.example` update with all new env vars (`BIGQUERY_PROJECT`, `BQ_METRICS_CACHE_TTL_SECONDS`, `ORACLE_*`, `MSA_*`). Note: `.env*` is blocked from direct write — must be done by user manually.
> - [ ] MSAL auth — currently local-dev bypass. Out of scope for now but flagged in plan §12.

## 5. Current Work

Final task before this handoff was **redesigning the pagination toolbar** in `frontend/src/app/features/live/live-locations-page/live-locations-page.component.{html,scss}`:

- Moved the `.pager` block from spanning the full page width into a new `.table-col` wrapper inside `.content`, so it sits aligned above the table column (right of the filter sidebar).
- Styled as a card: white surface, light border, rounded corners.
- Buttons grouped tightly on the left (`‹‹ ‹ Page N of M › ››` with tabular-numerics page indicator); meta on the right (`101–150 of 2181 · filtered from 2603` + Rows selector).

Immediately before pagination, the seller-color/legend work in `live-map-page.component.ts` added:
- `effectiveSellerKey(r)`, `effectiveSellerName(r)`, `sellerColor(key)` helpers (16-step palette, hash-based).
- `legend` computed signal — sorted top sellers + counts.
- `divergenceCount` computed signal — pins whose effective seller diverges from live (status ∈ {changed, stale}).
- Paint expressions updated: `'circle-color': ['get', 'color']`; `'circle-stroke-color': ['case', ['get', 'selected'], '#0f1722', ['match', ['get', 'lat_source'], 'census', '#b25b00', '#ffffff']]`.

Then **plan-live.md** got the final update of the session: status banner refreshed, phase table broken into 3a/3b/3c rows, API surface table split into read/write/deferred, architecture diagram now includes `live_assign.py` and the assignment tables.

## 6. Next Step

User most recently asked to "update the plan with latest" — done. Logical next step is one of:

1. **Ship Phase 3c-1 (reconfirm action)** — small, closes out §10a Surface A. ~30 min. Add a "Re-confirm" button visible only when `status === 'stale'` in `LiveAssignPanelComponent`; new effect calls a yet-to-add `PATCH ... ?reconfirm=true` (or repurpose existing patch with `change_source='reconfirm'`).
2. **Ship Phase 3c-2 (home dashboard tile)** — even smaller. Reuses `changesSummary()` API.
3. **Wait for prod-msa single-location URL** to unblock Phase 2b.4 seller-candidate panel.

Recommend 1 + 2 together (small, finishes the change-tracking story). Don't start tangential work unless the user asks.
