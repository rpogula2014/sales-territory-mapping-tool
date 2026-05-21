export interface LiveDc {
  region?: string;
  market?: string;
  dc_id?: number;
  dc_name?: string;
  [key: string]: unknown;
}

export interface LiveLocation {
  // From /siteuse
  siteUseID: string;
  locationNumber: string | null;
  customerId: number | null;
  primaryDcId: number | null;
  siteUseCode: string | null;
  siteUseStatus: string | null;
  primarySalesRepId: number | null;
  salesrepName: string | null;
  creditHold: string | null;
  marketingProgAtd: string | null;
  marketingProgVendor: string | null;

  // From BigQuery (when withMetrics=true)
  customer_cd?: string | null;
  dba_name?: string | null;
  address?: string | null;
  city_name?: string | null;
  state_cd?: string | null;
  county_name?: string | null;
  zip_cd?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  delivery_tier?: string | null;
  tire_pros?: string | null;
  customer_group_name?: string | null;
  customer_class_name?: string | null;
  customer_channel_name?: string | null;
  mtdsales?: number | null;
  ytdsales?: number | null;
  mtdunits?: number | null;
  ytdunits?: number | null;
  priorytdsales?: number | null;

  // Provenance for lat/lng: 'source' (BQ), 'census' (geocoded), or null.
  lat_source?: 'source' | 'census' | null;

  // §10a derived block — backend attaches this when assignments are merged.
  assignment?: AssignmentBlock;
}

export type AssignmentStatus = 'unchanged' | 'assigned' | 'changed' | 'stale';

export interface AssignmentBlock {
  status: AssignmentStatus;
  sellerId?: number | null;
  sellerName?: string | null;
  previousSellerId?: number | null;
  previousSellerName?: string | null;
  assignedAt?: string | null;
  assignedBy?: string | null;
  version?: number;
}

export interface ChangeRow {
  siteUseID: string;
  locationNumber: string | null;
  customerId: number | null;
  dcId: number | null;
  dcName: string | null;
  market: string | null;
  region: string | null;
  currentSellerId: number | null;
  currentSellerName: string | null;
  previousSellerId: number | null;
  previousSellerName: string | null;
  assignmentChanged: boolean;
  assignedBy: string | null;
  assignedAt: string | null;
  version: number;
}

export interface ChangesPage {
  total: number;
  limit: number;
  offset: number;
  rows: ChangeRow[];
}

export interface ChangesSummary {
  total: number;
  changed: number;
  byRegion: { region: string; count: number }[];
  byDc: { dcId: number; count: number }[];
}

export interface BulkAssignInput {
  siteUseIds: string[];
  sellerId: number | null;
  sellerName: string | null;
  dcId?: number | null;
  dcName?: string | null;
  market?: string | null;
  region?: string | null;
  liveBySite?: Record<string, Record<string, unknown>>;
  expectedVersions?: Record<string, number>;
}

export interface BulkConflict {
  siteUseId: string;
  expected: number;
  actual: number;
}

export interface BulkResult {
  ok: string[];
  conflicts: BulkConflict[];
}

export interface AssignmentPatchInput {
  sellerId: number | null;
  sellerName: string | null;
  liveSellerId: number | null;
  liveSellerName: string | null;
  expectedVersion: number;
  dcId?: number | null;
  dcName?: string | null;
  market?: string | null;
  region?: string | null;
  locationNumber?: string | null;
  customerId?: number | null;
}

export type FilterControl =
  | 'toggle'
  | 'range'
  | 'multiselect'
  | 'multiselect-tokens'
  | 'text';

export interface FilterOption {
  value: string;
  count: number;
}

export interface FilterDescriptor {
  field: string;
  label: string;
  control: FilterControl;
  options?: FilterOption[];
  min?: number;
  max?: number;
  separator?: string;
}

/** Active filter value indexed by field name. Shape depends on control type:
 *  toggle:             true | false | null
 *  range:              [min, max] | null
 *  multiselect:        string[] | null  (OR semantics)
 *  multiselect-tokens: string[] | null  (any-overlap)
 *  text:               string | null
 */
export type FilterValue =
  | boolean
  | [number, number]
  | string[]
  | string
  | null;

export type ActiveFilters = Record<string, FilterValue>;
