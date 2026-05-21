# Sales Territory Mapping Tool - Implementation Plan

## 1. Goal

Build an internal web app that lets sales leaders map customer accounts by address, assign each account to a seller, save those assignments, and export the updated Excel for downstream sales operations.

The app replaces the current Google My Maps workflow, which cannot handle the row volume and does not support filtering by business attributes during territory planning.

## 2. Core Workflow

1. Admin uploads Cynthia's Excel file.
2. Backend creates an async import job and returns immediately.
3. Backend validates required columns in the background.
4. Backend converts addresses to coordinates using batch geocoding.
5. Backend saves accounts, coordinates, seller assignments, seller list, and original Excel row data.
5. Editor logs in with company SSO.
6. Editor selects an assigned market.
7. App shows account pins on the map.
8. Editor filters accounts by seller, Tire Pros, Activate, Primary Program, Secondary Program, TTM Volume, Market, and DC.
9. Editor clicks one pin and assigns it to a seller, or rectangle-selects multiple pins and bulk assigns them.
10. Backend saves assignment changes.
11. Next login shows the saved assignment state.
12. User exports Excel with original columns plus assignment output columns.

Extra account attributes from the Excel can also be saved with each location and used as filters. Example: segment, priority tier, sales rep notes, customer type, opportunity size, or any future business field Cynthia adds.

## 2a. Current Implementation Status

### Implemented

- FastAPI backend scaffold with `/health`, OpenAPI docs, API router layout, local-dev auth bypass.
- PostgreSQL/PostGIS local database via Docker Compose on port `55432`.
- Alembic setup with initial schema for users, markets, datasets, accounts, sellers, assignment events, and import jobs.
- UUID v7 app-generated primary keys.
- Market APIs:
  - `GET /api/markets`
  - `POST /api/markets` for local/admin market creation.
- Dataset APIs:
  - `GET /api/datasets`
  - `POST /api/datasets/import`
  - `GET /api/datasets/{dataset_id}/import-status`
  - `GET /api/datasets/{dataset_id}/accounts`
  - `GET /api/datasets/{dataset_id}/sellers`
  - `GET /api/datasets/{dataset_id}/export`
- Excel import parser:
  - validates required columns.
  - preserves original row JSON.
  - stores extra columns in `extra_attributes_json`.
  - normalizes booleans and numeric sales fields.
- Async import job path:
  - creates dataset/import job.
  - parses Excel in background.
  - creates normalized sellers per market.
  - imports accounts with provided `Latitude`/`Longitude`.
  - calls Census batch geocoder for rows missing provided coordinates.
  - records match/failure state and matched address for manual correction.
  - carries forward previous assignments by `Customer Number` on re-import.
  - marks dataset active after successful import.
- Account GeoJSON endpoint:
  - server-side filters for seller, DC, Tire Pros, Activate, Primary Program, Secondary Program, TTM min/max, and `bbox`.
  - returns pin number, seller color, assignment version, and account properties.
- Assignment backend endpoints:
  - `PATCH /api/accounts/{account_id}/assignment` with optimistic `version` check.
  - `POST /api/accounts/bulk-assignment` all-or-nothing validation path.
- Excel export:
  - backend `.xlsx` streaming endpoint.
  - full dataset export.
  - filtered view export using the same filter params as the map.
  - preserves original columns and appends assignment/geocode output columns.
- Angular frontend scaffold:
  - routes for markets, map, and admin import.
  - API service.
  - import page with market dropdown, upload, status polling, and validation error display.
  - market/dataset picker.
  - MapLibre map page.
- Map UX:
  - OSM raster fallback for local dev when MapTiler key is blank.
  - all locations render as individual pin icons; clustering removed for current UX.
  - pins are colored by seller.
  - pin numbers render on individual pins.
  - selected pin highlights as larger orange pin.
  - click pin to show detail panel.
  - seller/DC filter controls.
  - selected-account seller dropdown and save assignment button.
  - `409 Conflict` handling with account refresh.
  - rectangle-select mode for bulk selection.
  - selected account list/count and bulk seller assignment.
  - full and filtered Excel export actions.
  - sidebar counts for locations, visible pins/rendered pins, and selected pins.
- Sample files:
  - `sample-data/southern-california-10-accounts.xlsx`
  - `sample-data/southern-california-200-accounts.xlsx`
- Verification run:
  - backend `ruff` passes.
  - backend compile/OpenAPI checks pass.
  - Alembic SQL generation passes.
  - frontend `npm run build` passes.

### Pending

- Microsoft Entra auth:
  - frontend MSAL login/token refresh.
  - backend JWT validation against Entra issuer/audience/JWKS.
  - remove local-dev auth bypass for production.
- Access management:
  - user provisioning.
  - market access admin path.
  - Entra group mapping if required.
- Dynamic extra filters:
  - configure approved filterable extra fields.
  - render category/boolean/range/date controls.
  - apply `extra.<fieldName>` filters in backend.
- Production basemap:
  - restore MapTiler style URL when key/procurement exists.
  - domain restrict key.
  - usage alerts/cap.
- Tests:
  - backend tests for parser/import/re-import/assignment.
  - frontend tests for import/map/filter/assignment.
  - committed sanitized test fixture set under `backend/tests/fixtures`.
- Deployment hardening:
  - production Docker image validation.
  - migration run command in deploy flow.
  - structured logging without PII.
  - assignment event retention cleanup job.

### Known Current Constraints

- Missing lat/lng rows import as `geocode_status = failed`; real geocoding is not implemented yet.
- Map uses public OSM raster tiles locally when `mapStyleUrl` is empty; production should use approved tile provider.
- Auth is local-dev bypass by default.
- Clustering is intentionally removed in current UI based on user feedback; if row counts grow, revisit clustering/server-side tiling.
- Assignment UI supports single and bulk save, but has not been covered by automated frontend tests yet.

## 3. Architecture

### 3.1 Frontend

- Angular single-page app.
- MapLibre for interactive map rendering.
- MapTiler for basemap tiles only.
- Angular HttpClient for backend calls.
- Angular signals for local UI state.
- No private customer data is sent to MapTiler.

Frontend responsibilities:

- Authenticate through Microsoft Entra redirect flow.
- Load visible markets/datasets for logged-in user.
- Render MapTiler basemap through MapLibre.
- Render private account pins from backend data.
- Apply filters through backend query params; backend is source of truth for filtered account data.
- Render dynamic filters for approved extra account attributes.
- Send assignment saves to backend.
- Trigger Excel export download.
- Refresh Entra access tokens silently during long map sessions.

### 3.2 Backend

- FastAPI REST API.
- PostgreSQL with PostGIS.
- SQLAlchemy for data access.
- Alembic for migrations.
- Microsoft Entra JWT validation.
- Pandas/openpyxl for Excel import/export.
- US Census Geocoder for batch address geocoding.
- Background worker for long-running imports/geocoding.

Backend responsibilities:

- Validate identity and role.
- Enforce market-level access.
- Import Excel files.
- Geocode addresses once during import.
- Persist account records and assignment state.
- Maintain normalized seller list per market.
- Save single and bulk assignment changes.
- Export updated Excel.

### 3.3 Database

Use PostgreSQL as the application source of truth. Use PostGIS for point geometry now and future spatial features later.

Required extension:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

All primary keys must use UUID v7.

## 4. Basemap Provider

Use MapTiler for v1 basemap tiles.

MapTiler provides:

- Streets
- Highways
- City labels
- Boundaries
- Map background

MapTiler does not receive:

- Account names
- Customer numbers
- Sales volume
- Seller assignments
- Excel file contents
- Private filters

Runtime map layering:

```txt
MapLibre canvas
  layer 1: MapTiler basemap
  layer 2: account pins from backend
  layer 3: pin labels
  layer 4: selection overlays
```

Prefer MapTiler SDK session billing if possible. For internal commercial use, assume paid Flex tier unless procurement approves another provider. Keep basemap integration isolated so Esri, Mapbox, or self-hosted tiles can replace MapTiler later.

Before launch:

- restrict MapTiler API key by production domain.
- configure MapTiler usage budget/cap if account supports it.
- configure usage alert at 50%, 80%, and 100% of monthly quota.
- document fallback basemap provider or temporary no-basemap degraded mode.

## 5. Authentication and Authorization

### 5.1 Authentication

Use Microsoft Entra SSO.

Frontend:

- Redirect user to Entra login.
- Receive token after login.
- Send bearer token to FastAPI.
- Use silent token refresh before expiry.
- If refresh fails, block saves and prompt user to log in again without dropping current UI state.

Backend:

- Validate JWT issuer, audience, signature, and expiry.
- Map Entra subject/email to local `users` row.
- Return current user via `GET /api/me`.

### 5.2 Roles

Use two roles for v1:

- `admin`: import Excel, view assigned markets, edit assignments, export.
- `editor`: view assigned markets, edit assignments, export.

No public registration. Users are provisioned by admin or synced from approved Entra groups.

### 5.3 Market Access

Use market-level access control.

- User can only view datasets for assigned markets.
- User can only edit accounts in assigned markets.
- User can only export assigned markets.
- DC is a filter inside market, not a permission boundary.

## 6. Data Model

### 6.1 `users`

Stores local app identity mapped to Entra.

Fields:

- `id`
- `entra_subject`
- `email`
- `name`
- `role`
- `created_at`
- `last_login_at`

### 6.2 `markets`

Stores market definitions.

Fields:

- `id`
- `name`
- `region`
- `created_at`

### 6.3 `user_market_access`

Maps users to markets.

Fields:

- `user_id`
- `market_id`

Unique constraint:

- `(user_id, market_id)`

### 6.4 `datasets`

Represents one imported Excel file or market subset.

Fields:

- `id`
- `name`
- `market_id`
- `source_filename`
- `uploaded_by`
- `uploaded_at`
- `row_count`
- `geocode_success_count`
- `geocode_failure_count`
- `import_status`
- `parent_dataset_id`
- `is_active`

Allowed `import_status` values:

- `pending`
- `processing`
- `completed`
- `completed_with_warnings`
- `failed`

### 6.5 `accounts`

Stores imported account rows and current assignment state.

Fields:

- `id`
- `dataset_id`
- `customer_number`
- `account_name`
- `address`
- `city`
- `state`
- `zip`
- `latitude`
- `longitude`
- `geom`
- `geocode_status`
- `matched_address`
- `suggested_seller`
- `current_seller`
- `seller_id`
- `mtd_sales`
- `ytd_sales`
- `ttm_volume`
- `tire_pros`
- `activate`
- `primary_program`
- `secondary_program`
- `market`
- `dc`
- `original_row_json`
- `extra_attributes_json`
- `assignment_changed`
- `assigned_at`
- `assigned_by`
- `created_at`
- `updated_at`
- `version`

Constraints:

- `(dataset_id, customer_number)` unique.
- `geom` nullable for failed geocode rows.
- `version` increments on every assignment update for optimistic locking.

### 6.6 `sellers`

Stores normalized seller options per market.

Fields:

- `id`
- `market_id`
- `display_name`
- `normalized_name`
- `color`
- `is_active`
- `created_at`
- `updated_at`

Constraints:

- `(market_id, normalized_name)` unique.

Seller rules:

- Import builds seller list from `Suggested Seller` values.
- Assignment dropdown uses `sellers`, not free text.
- API accepts `seller_id` for saves.
- Display keeps `display_name`.
- Pin colors come from `sellers.color`.
- Unknown imported sellers create inactive-review warnings if normalization cannot match safely.

### 6.7 `assignment_events`

Stores audit history for assignment changes.

Fields:

- `id`
- `account_id`
- `old_seller`
- `new_seller`
- `old_seller_id`
- `new_seller_id`
- `changed_by`
- `changed_at`
- `change_source`
- `account_version`

Allowed `change_source` values:

- `single`
- `bulk`
- `import`

Retention:

- Keep assignment events for 18 months by default.
- Keep only account ID, seller IDs/names, editor ID, timestamp, and source.
- Do not store full original account row in assignment event records.
- Retention can be shortened if legal/security requires it.

### 6.8 `import_jobs`

Tracks long-running Excel import/geocoding work.

Fields:

- `id`
- `dataset_id`
- `status`
- `uploaded_by`
- `started_at`
- `finished_at`
- `row_count`
- `processed_count`
- `geocode_success_count`
- `geocode_failure_count`
- `error_message`
- `warnings_json`

Allowed `status` values:

- `queued`
- `processing`
- `completed`
- `completed_with_warnings`
- `failed`

## 7. Excel Import

### 7.1 Required Columns

Confirm exact names against Cynthia's real file before final implementation. Initial expected columns:

- `Account Name`
- `Customer Number`
- `Address`
- `City`
- `State`
- `Zip`
- `Suggested Seller`
- `MTD Sales`
- `YTD Sales`
- `TTM Volume`
- `Tire Pros`
- `Activate`
- `Primary Program`
- `Secondary Program`
- `Market`
- `DC`

Optional input columns:

- `Latitude`
- `Longitude`

Additional non-required business columns are allowed. The import should preserve them in `original_row_json`; approved filterable fields should also be copied into `extra_attributes_json`.

### 7.2 Import Validation

Reject import if:

- Required columns are missing.
- Customer Number is blank.
- Customer Number duplicates inside same file.
- Market is blank.
- Uploaded file is not `.xlsx`.

Allow import with warnings if:

- Address fields are incomplete.
- Geocoding fails.
- numeric fields are blank or non-numeric.
- boolean fields need normalization.
- extra columns are present but not configured as filterable.

### 7.3 Field Normalization

Normalize booleans:

- true values: `true`, `yes`, `y`, `1`, `x`
- false values: `false`, `no`, `n`, `0`, blank

Normalize numbers:

- remove commas and currency symbols.
- blank becomes `0` for sales/volume fields.

Normalize seller:

- trim whitespace.
- preserve original casing for display.

### 7.4 Extra Data Points

Support additional data points per account/location without schema changes for every new business field.

Examples:

- customer segment.
- priority tier.
- account status.
- opportunity size.
- product category.
- service level.
- last contact date.
- custom notes.

Storage rules:

- Always preserve all original Excel columns in `original_row_json`.
- Store approved filterable extra fields in `extra_attributes_json`.
- Do not expose every random Excel column as a filter automatically.
- Admin can configure which extra fields are filterable during import or through a simple backend config.

Filter types:

- text/category fields use dropdown or multi-select.
- boolean fields use checkbox/toggle.
- numeric fields use min/max range.
- date fields use start/end date range.

V1 default:

- Build dynamic filter support in API and frontend.
- Configure filterable extra fields server-side, not user-editable UI.
- Start with known fields from discovery, then add more once real Excel sample arrives.

## 8. Geocoding

### 8.1 Provider

Use US Census Geocoder batch endpoint for v1.

Endpoint:

```txt
https://geocoding.geo.census.gov/geocoder/locations/addressbatch
```

Batch CSV format:

```csv
unique_id,street,city,state,zip
```

### 8.2 Geocoding Rules

- If valid Latitude/Longitude already exists in Excel, use it.
- If coordinates are missing, send address to Census batch geocoder.
- Process in chunks of 10,000 rows.
- Save returned latitude/longitude and matched address.
- Mark unmatched rows as `geocode_status = failed`.
- Failed geocode rows remain in dataset but are not shown as map pins.
- Geocoding runs in background import job, not inside the HTTP upload request.
- Census timeout or failure marks affected rows as failed and completes import with warnings if other rows succeed.

### 8.3 Fallback Strategy

V1 fallback is explicit manual correction loop.

- No secondary paid geocoder in v1 unless procurement approves one.
- If Census fails or misses addresses, export/import corrected Excel with Latitude/Longitude added.
- Re-import uses provided coordinates and bypasses Census for corrected rows.
- Track geocode failures in import summary so admin can fix only failed rows.

Candidate future fallback providers:

- Esri geocoding if company already has ArcGIS licensing.
- MapTiler geocoding if procurement approves usage cost.
- Self-hosted Nominatim if avoiding external geocoding vendors matters more than ops simplicity.

### 8.4 Manual Correction

V1 correction path:

- Export/import corrected Excel with Latitude/Longitude added.
- Do not build map-click coordinate correction unless stakeholders require it after first test import.

This keeps v1 smaller and avoids a separate correction UI.

## 8.5 Dataset Re-import

Re-import is required because Cynthia may provide updated Excel files after initial assignment work.

Default behavior:

- Re-import creates a new dataset version linked by `parent_dataset_id`.
- Match rows by `Customer Number` within same market.
- Carry forward saved assignment from previous active dataset when `Customer Number` matches.
- Use new Excel values for address, sales, program, extra attributes, Market, and DC.
- If address changes and no valid lat/lng is provided, geocode again.
- New customer numbers get suggested/current seller from imported file.
- Removed customer numbers remain only in old dataset version.
- New import becomes active only after import job completes.
- Failed import does not replace active dataset.

This avoids losing saved assignments while still preserving historical imports.

## 9. API Design

All endpoints require authenticated user unless noted.

### 9.1 Auth

#### `GET /api/me`

Returns current user.

Response:

```json
{
  "id": "uuid",
  "email": "user@company.com",
  "name": "User Name",
  "role": "editor",
  "markets": [
    {
      "id": "uuid",
      "name": "Southern California"
    }
  ]
}
```

### 9.2 Markets

#### `GET /api/markets`

Returns markets visible to current user.

### 9.3 Datasets

#### `GET /api/datasets`

Query params:

- `marketId`

Returns datasets visible to current user.

#### `POST /api/datasets/import`

Admin only. Multipart file upload. Returns `202 Accepted`; import/geocoding runs asynchronously.

Form fields:

- `file`
- `marketId`
- `datasetName`

Response:

```json
{
  "datasetId": "uuid",
  "importJobId": "uuid",
  "status": "queued"
}
```

#### `GET /api/datasets/{dataset_id}/import-status`

Admin only. Polls import progress.

Response:

```json
{
  "datasetId": "uuid",
  "importJobId": "uuid",
  "status": "processing",
  "rowCount": 12500,
  "processedCount": 8000,
  "geocodeSuccessCount": 7600,
  "geocodeFailureCount": 400,
  "warnings": []
}
```

### 9.4 Accounts

#### `GET /api/datasets/{dataset_id}/accounts`

Returns account points and properties.

Query params:

- `dc`
- `seller`
- `tirePros`
- `activate`
- `primaryProgram`
- `secondaryProgram`
- `ttmMin`
- `ttmMax`
- `bbox`
- `format`
- `extra.<fieldName>`

Supported formats:

- `json`
- `geojson`

For map rendering, frontend should request `geojson`.

#### `PATCH /api/accounts/{account_id}/assignment`

Updates one account assignment.

Request:

```json
{
  "sellerId": "uuid",
  "version": 3
}
```

Response:

```json
{
  "accountId": "uuid",
  "sellerId": "uuid",
  "currentSeller": "Jane Smith",
  "assignmentChanged": true,
  "assignedAt": "2026-05-19T18:00:00Z",
  "assignedBy": "user@company.com",
  "version": 4
}
```

If `version` is stale, return `409 Conflict` with current account assignment/version. Frontend must show conflict and ask user to reload/apply again.

#### `POST /api/accounts/bulk-assignment`

Updates multiple accounts.

Request:

```json
{
  "accountIds": ["uuid-1", "uuid-2"],
  "sellerId": "uuid"
}
```

Response:

```json
{
  "updatedCount": 2,
  "sellerId": "uuid",
  "seller": "Jane Smith"
}
```

Bulk assignment is all-or-nothing:

- If any account ID is not found, inaccessible, from another dataset, or stale when versions are supplied, reject entire batch.
- Return `400` or `403` with offending account IDs.
- Do not partially update.

Optional request shape with versions:

```json
{
  "accounts": [
    {
      "accountId": "uuid-1",
      "version": 3
    }
  ],
  "sellerId": "uuid"
}
```

### 9.5 Export

#### `GET /api/datasets/{dataset_id}/export`

Query params match account filters:

- `dc`
- `seller`
- `tirePros`
- `activate`
- `primaryProgram`
- `secondaryProgram`
- `ttmMin`
- `ttmMax`

Returns `.xlsx`.

Default behavior:

- If no filter params are provided, export full active dataset for current market access.
- If filter params are provided, export only filtered scope.
- UI must label this clearly: `Export full dataset` and `Export current filtered view`.

Export includes original columns plus:

- `New Seller`
- `Assignment Changed`
- `Assigned At`
- `Assigned By`

## 10. Frontend UX

### 10.1 Routes

- `/login`
- `/markets`
- `/map/:datasetId`
- `/admin/import`

### 10.2 Market Picker

Shows:

- visible markets.
- available datasets per market.
- import button for admins.

### 10.3 Map Screen

Layout:

- full-screen map.
- left sidebar for filters and seller summary.
- right panel or popup for selected account detail.
- bottom action bar for selected pins and bulk reassignment.

Filters:

- seller multi-select from normalized market seller list.
- Tire Pros toggle.
- Activate toggle.
- Primary Program dropdown.
- Secondary Program dropdown.
- TTM Volume min/max.
- DC dropdown.
- dynamic extra filters from approved account attributes.

Seller summary:

- seller name.
- visible account count.
- visible TTM total.

### 10.4 Pin Detail

When user clicks pin, show:

- account name.
- customer number.
- address.
- current seller.
- suggested seller.
- TTM Volume.
- Tire Pros.
- Activate.
- Primary Program.
- Secondary Program.
- approved extra attributes.
- seller assignment dropdown.
- save button.

### 10.5 Selection

V1 selection:

- rectangle select accounts inside rectangle bounds.
- selected pins highlighted.
- bulk action bar shows selected count.
- user chooses seller and applies bulk assignment.

Freehand lasso can be added after rectangle selection if time remains.

Cluster selection rule:

- At street zoom where clustering is disabled, rectangle select runs client-side over rendered pins.
- When clusters are visible, frontend sends rectangle `bbox` plus current filters to backend.
- Backend returns matching underlying account IDs, not cluster bubble IDs.
- Selection ignores `geocode_status = failed` rows.

## 11. Map Rendering

Use MapLibre with a GeoJSON source.

Source:

- `accounts`
- clustering enabled.

Layers:

- `account-clusters`
- `account-cluster-count`
- `account-pins`
- `account-selected-pins`

Pin color:

- seller color from normalized `sellers` table.
- changed assignments use `current_seller`.
- unassigned/blank seller uses neutral gray.

Clustering:

- cluster at low zoom.
- disable clustering at street zoom around 15+.
- clicking cluster zooms to expansion zoom.

Dense areas:

- use circle/symbol layers, not thousands of HTML markers.
- handle overlapping points by showing feature list when multiple pins are clicked at same point.

## 12. Save Behavior

Single assignment:

- user changes seller on selected pin.
- frontend calls `PATCH /api/accounts/{id}/assignment`.
- backend validates market access.
- backend validates account `version`.
- backend saves current seller and assignment event.
- frontend updates local account state.
- stale version returns `409 Conflict`; frontend reloads account detail and shows current saved seller.

Bulk assignment:

- user rectangle-selects pins.
- frontend sends selected account IDs to bulk endpoint.
- backend validates all account IDs are accessible.
- backend validates selected accounts belong to same dataset and market.
- backend updates accounts in one transaction.
- backend writes assignment events.
- frontend updates selected accounts locally or reloads account data.
- bulk assignment is all-or-nothing; any invalid/inaccessible account rejects whole request.

No optimistic-only saves. UI should show save progress and error state.

## 13. Export Behavior

Export full active dataset by default.

The UI must provide two explicit actions:

- `Export full dataset`
- `Export current filtered view`

Export must:

- include same row count as selected export scope.
- preserve original source columns from `original_row_json`.
- append output columns.
- use saved assignment values from database.

Do not promise full Excel formatting fidelity in v1 unless tested against Cynthia's downstream file. Minimum acceptance is preserving row values, column order, and added assignment columns.

## 14. Error Handling

Import errors:

- missing columns.
- invalid file type.
- duplicate customer numbers.
- empty market.

Geocode warnings:

- unmatched address.
- incomplete address.
- invalid existing lat/lng.

Runtime errors:

- unauthorized.
- token expired.
- forbidden market.
- dataset not found.
- account not found.
- assignment conflict.
- assignment save failed.
- export failed.

Frontend should show clear user-facing messages and avoid losing unsaved visible state.

## 15. Security Requirements

- Enforce auth server-side, not only in Angular.
- Validate JWT on every API request.
- Enforce market access on every account and export query.
- Do not expose database IDs across markets without access checks.
- Store MapTiler key as browser config and restrict it by domain in MapTiler dashboard.
- Do not send private account data to MapTiler.
- Do not log full Excel rows or customer sales details in application logs.
- Do not log full geocoder request files.
- Keep assignment event history for 18 months by default, then purge or archive according to company retention policy.
- Never run Terraform apply as part of this project workflow.

## 16. Deployment Shape

Recommended v1 deployment:

- Angular static build served by nginx or internal static hosting.
- FastAPI container.
- PostgreSQL/PostGIS managed database or internal database instance.
- Environment variables for:
  - database URL.
  - Entra tenant/client/audience.
  - MapTiler API key.
  - Census geocoder timeout/chunk settings.
  - import worker concurrency.
  - assignment event retention period.

## 17. Testing Plan

### Backend Tests

- Excel import succeeds with valid sample file.
- Import rejects missing required columns.
- Import rejects duplicate customer numbers.
- Existing Latitude/Longitude bypasses geocoding.
- Missing coordinates triggers mocked Census geocoding.
- Failed geocodes are stored and excluded from GeoJSON map output.
- Import endpoint returns `202 Accepted` and status endpoint reports progress.
- Re-import carries forward saved assignments by `Customer Number`.
- Failed re-import does not replace active dataset.
- Seller list is normalized per market and assignment uses `seller_id`.
- Admin can import.
- Editor cannot import.
- User cannot access unassigned market.
- Single assignment updates account and writes event.
- Stale single assignment version returns `409 Conflict`.
- Bulk assignment updates accessible accounts in one transaction.
- Bulk assignment rejects entire batch when one account is inaccessible.
- Export includes original columns plus output assignment columns.
- Export without filters returns full active dataset.
- Export with filters returns filtered scope.
- Extra filterable account attributes can filter map pins and summary totals.

### Frontend Tests

- Login route redirects to Entra.
- Token refresh keeps long map session active; failed refresh blocks saves and prompts login.
- Market picker shows only accessible markets.
- Import page hidden or blocked for non-admin.
- Import page polls job status after upload.
- Map page loads dataset accounts.
- Filters update visible pins and seller summary.
- Clicking pin opens account detail.
- Single assignment saves and updates pin color.
- Rectangle select highlights selected pins.
- Rectangle select works at cluster zoom by querying backend with `bbox`.
- Bulk assignment updates selected pins.
- Conflict response reloads account state and shows current saved seller.
- Refresh reloads saved assignment state.
- Export button downloads `.xlsx`.

### End-to-End Scenarios

1. Admin imports one-market Excel file and sees import summary.
2. Admin watches import job progress until completed.
3. Editor opens market map and sees pins.
4. Editor filters to Tire Pros accounts and assigns one pin.
5. Second editor conflict on same pin returns `409`.
6. Editor rectangle-selects visible unclustered accounts and bulk assigns seller.
7. Editor reloads page and sees saved assignments.
8. Admin re-imports newer Excel and saved assignments carry forward by customer number.
9. Editor exports full dataset and filtered view, then verifies assignment columns.

### Test Fixtures

Commit sanitized test fixtures under `tests/fixtures/`:

- `valid_accounts.xlsx`
- `missing_required_columns.xlsx`
- `duplicate_customer_numbers.xlsx`
- `existing_coordinates.xlsx`
- `reimport_changed_rows.xlsx`

Fixtures must contain fake customer names, fake addresses, and no real sales data.

## 18. Delivery Milestones

### Milestone 1: Foundation

- FastAPI project scaffold.
- Angular project scaffold.
- Postgres/PostGIS schema migration.
- Entra auth validation.
- MapTiler basemap renders in Angular.

### Milestone 2: Import and Persistence

- async Excel import endpoint and status polling.
- required column validation.
- geocoding integration.
- re-import merge by customer number.
- account persistence.
- seller persistence.
- dataset/market APIs.

### Milestone 3: Map and Filters

- account GeoJSON endpoint.
- server-side filter and `bbox` selection support.
- MapLibre account layers.
- clustering.
- sidebar filters.
- seller summary.

### Milestone 4: Assignment

- pin detail panel.
- single assignment save.
- rectangle selection.
- bulk assignment save.
- assignment event history.

### Milestone 5: Export and Hardening

- Excel export endpoint.
- access-control tests.
- import/export validation with real sample file.
- performance test with target row count.
- user test with Cynthia/RSD workflow.

## 19. Open Items

Resolve before implementation starts:

- Get real Excel sample from Cynthia.
- Confirm exact column names and data types.
- Identify additional business columns that should become filters.
- Confirm target row count for full West region.
- Confirm company Entra app registration details.
- Confirm MapTiler procurement/API key/domain restrictions.
- Confirm MapTiler usage cap/alert setup.
- Confirm hosting target.
- Confirm downstream Excel consumer and required export fidelity.
- Confirm assignment event retention requirement with security/legal.

## 19a. Resolved Design Decisions

### Concurrency on assignment

- `accounts` row carries `version` integer (incremented per assignment change) and `updated_at`.
- `PATCH /api/accounts/{id}/assignment` request body includes expected `version`.
- Server compares; mismatch returns `409 Conflict` with current row state.
- Frontend reloads pin and prompts user to redo edit.

### Bulk assignment partial failure

- All-or-nothing. Single transaction.
- If any account in batch fails market-access or version check, whole batch rejected.
- Response: `409` with `failedAccountIds` array and reason per id.
- No partial commits. No silent skips.

### MapTiler usage cap

- Set MapTiler dashboard hard monthly cap before launch.
- Restrict API key by referrer domain.
- Alert at 70% / 90% monthly quota via MapTiler email.
- Consider backend `/api/maptiler-token` short-lived signed token endpoint in v1.1 if procurement key supports it.

### Pin Rendering + Rectangle Selection

- Current UX shows all returned accounts as individual pins. Clustering is removed based on user feedback.
- Rectangle select operates on underlying account features inside rectangle bounds.
- Backend `GET /api/datasets/{id}/accounts` accepts `bbox` param for server-side rectangle queries.
- Selection ignores `geocode_status = failed` rows.

### Client vs server filter

- Backend filter is source of truth. `GET /api/datasets/{id}/accounts` always applies filter params server-side.
- Frontend re-fetches on filter change. No client-side filter on top of partial data.
- Row ceiling v1: <= 50k accounts per dataset. Beyond that, add server-side tiling.

### UUID v7

- All primary keys use UUID v7 (time-ordered, K-sortable).
- Backend: Python `uuid.uuid7()` (3.13+) or `uuid6.uuid7()` lib.
- Postgres: `uuidv7()` (PG 18+); else app-generated at insert.

### Token refresh

- Frontend uses MSAL silent token renewal before expiry.
- Backend rejects expired tokens with `401`; frontend intercepts, triggers silent refresh, retries original request once.
- On refresh failure: redirect to `/login`, preserve unsaved selection state in sessionStorage.

## 20. Defaults Chosen

- Angular SPA instead of React.
- FastAPI backend.
- PostgreSQL + PostGIS.
- Microsoft Entra SSO.
- Shared market state.
- Admin + Editor roles.
- Market-level access.
- Async backend import geocoding.
- US Census Geocoder for v1.
- Manual corrected-lat/lng loop as v1 geocoding fallback.
- MapTiler basemap.
- Rectangle selection first; lasso later if needed.
- Clustering removed for current UX; revisit if full production row counts create performance/readability issues.
- Export full dataset by default; filtered export is explicit.
- UUID v7 for primary keys.
- Optimistic locking with account `version`.
- Bulk assignment all-or-nothing.
