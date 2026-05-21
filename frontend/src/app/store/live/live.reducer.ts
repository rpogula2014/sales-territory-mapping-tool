import { createFeature, createReducer, createSelector, on } from '@ngrx/store';

import {
  ActiveFilters,
  FilterDescriptor,
  LiveDc,
  LiveLocation
} from '../../core/models/live.model';
import { LiveActions } from './live.actions';
import { applyFilters } from './live.filters';

export interface LiveState {
  regions: string[];
  markets: string[];
  dcs: LiveDc[];
  selectedRegion: string | null;
  selectedMarket: string | null;
  selectedDcId: number | null;
  locations: LiveLocation[];
  filterSchema: FilterDescriptor[];
  activeFilters: ActiveFilters;
  statusFilter: string[];
  saving: boolean;
  saveMessage: string | null;
  loadingRegions: boolean;
  loadingMarkets: boolean;
  loadingDcs: boolean;
  loadingLocations: boolean;
  loadingFilterSchema: boolean;
  error: string | null;
}

const initialState: LiveState = {
  regions: [],
  markets: [],
  dcs: [],
  selectedRegion: null,
  selectedMarket: null,
  selectedDcId: null,
  locations: [],
  filterSchema: [],
  activeFilters: {},
  statusFilter: [],
  saving: false,
  saveMessage: null,
  loadingRegions: false,
  loadingMarkets: false,
  loadingDcs: false,
  loadingLocations: false,
  loadingFilterSchema: false,
  error: null
};

export const liveFeature = createFeature({
  name: 'live',
  reducer: createReducer(
    initialState,
    on(LiveActions.loadRegions, (state) => ({ ...state, loadingRegions: true, error: null })),
    on(LiveActions.loadRegionsSuccess, (state, { regions }) => ({
      ...state,
      regions,
      loadingRegions: false
    })),
    on(LiveActions.loadRegionsFailure, (state, { error }) => ({
      ...state,
      loadingRegions: false,
      error
    })),

    on(LiveActions.regionSelected, (state, { region }) => ({
      ...state,
      selectedRegion: region,
      selectedMarket: null,
      selectedDcId: null,
      markets: [],
      dcs: [],
      locations: [],
      filterSchema: [],
      activeFilters: {}
    })),

    on(LiveActions.loadMarkets, (state) => ({ ...state, loadingMarkets: true, error: null })),
    on(LiveActions.loadMarketsSuccess, (state, { markets }) => ({
      ...state,
      markets,
      loadingMarkets: false
    })),
    on(LiveActions.loadMarketsFailure, (state, { error }) => ({
      ...state,
      loadingMarkets: false,
      error
    })),

    on(LiveActions.marketSelected, (state, { market }) => ({
      ...state,
      selectedMarket: market,
      selectedDcId: null,
      dcs: [],
      locations: [],
      filterSchema: [],
      activeFilters: {}
    })),

    on(LiveActions.loadDcs, (state) => ({ ...state, loadingDcs: true, error: null })),
    on(LiveActions.loadDcsSuccess, (state, { dcs }) => ({ ...state, dcs, loadingDcs: false })),
    on(LiveActions.loadDcsFailure, (state, { error }) => ({
      ...state,
      loadingDcs: false,
      error
    })),

    on(LiveActions.dcSelected, (state, { dcId }) => ({
      ...state,
      selectedDcId: dcId,
      locations: [],
      filterSchema: [],
      activeFilters: {}
    })),

    on(LiveActions.loadLocations, (state) => ({
      ...state,
      loadingLocations: true,
      error: null,
      locations: []
    })),
    on(LiveActions.loadLocationsSuccess, (state, { locations }) => ({
      ...state,
      locations,
      loadingLocations: false
    })),
    on(LiveActions.loadLocationsFailure, (state, { error }) => ({
      ...state,
      loadingLocations: false,
      error
    })),

    on(LiveActions.loadFilterSchema, (state) => ({ ...state, loadingFilterSchema: true })),
    on(LiveActions.loadFilterSchemaSuccess, (state, { schema }) => ({
      ...state,
      filterSchema: schema,
      loadingFilterSchema: false
    })),
    on(LiveActions.loadFilterSchemaFailure, (state) => ({ ...state, loadingFilterSchema: false })),

    on(LiveActions.setFilter, (state, { field, value }) => ({
      ...state,
      activeFilters: isEmpty(value)
        ? omit(state.activeFilters, field)
        : { ...state.activeFilters, [field]: value }
    })),
    on(LiveActions.clearFilters, (state) => ({ ...state, activeFilters: {}, statusFilter: [] })),
    on(LiveActions.setStatusFilter, (state, { statuses }) => ({ ...state, statusFilter: statuses })),

    on(
      LiveActions.saveAssignment,
      LiveActions.revertAssignment,
      LiveActions.reconfirmAssignment,
      (state) => ({ ...state, saving: true, saveMessage: null })
    ),
    on(LiveActions.saveAssignmentSuccess, (state, { siteUseId, assignment }) => ({
      ...state,
      saving: false,
      saveMessage: 'Assignment saved.',
      locations: state.locations.map((l) =>
        l.siteUseID === siteUseId ? { ...l, assignment } : l
      )
    })),
    on(LiveActions.revertAssignmentSuccess, (state, { siteUseId }) => ({
      ...state,
      saving: false,
      saveMessage: 'Local assignment cleared.',
      locations: state.locations.map((l) =>
        l.siteUseID === siteUseId
          ? { ...l, assignment: { status: 'unchanged' as const } }
          : l
      )
    })),
    on(LiveActions.reconfirmAssignmentSuccess, (state, { siteUseId, assignment }) => ({
      ...state,
      saving: false,
      saveMessage: 'Baseline reconfirmed.',
      locations: state.locations.map((l) =>
        l.siteUseID === siteUseId ? { ...l, assignment } : l
      )
    })),
    on(
      LiveActions.saveAssignmentFailure,
      LiveActions.revertAssignmentFailure,
      LiveActions.reconfirmAssignmentFailure,
      (state, { error }) => ({ ...state, saving: false, saveMessage: error })
    )
  )
});

function isEmpty(value: unknown): boolean {
  if (value == null) return true;
  if (Array.isArray(value) && value.length === 0) return true;
  if (typeof value === 'string' && value.trim() === '') return true;
  return false;
}

function omit<T extends Record<string, unknown>>(obj: T, key: string): T {
  const { [key]: _drop, ...rest } = obj;
  return rest as T;
}

export const {
  name: liveFeatureKey,
  reducer: liveReducer,
  selectRegions,
  selectMarkets: selectLiveMarkets,
  selectDcs,
  selectSelectedRegion,
  selectSelectedMarket,
  selectSelectedDcId,
  selectLocations,
  selectFilterSchema,
  selectActiveFilters,
  selectLoadingRegions,
  selectLoadingMarkets,
  selectLoadingDcs,
  selectLoadingLocations,
  selectLoadingFilterSchema,
  selectStatusFilter,
  selectSaving,
  selectSaveMessage,
  selectError: selectLiveError
} = liveFeature;

export const selectFilteredLocations = createSelector(
  selectLocations,
  selectActiveFilters,
  selectFilterSchema,
  selectStatusFilter,
  (locations, filters, schema, statuses) => {
    const base = applyFilters(locations, filters, schema);
    if (statuses.length === 0) return base;
    const want = new Set(statuses);
    return base.filter((r) => want.has(r.assignment?.status ?? 'unchanged'));
  }
);

const STATUSES = ['unchanged', 'assigned', 'changed', 'stale'] as const;

export const selectStatusCounts = createSelector(selectLocations, (locations) => {
  const counts: Record<string, number> = { unchanged: 0, assigned: 0, changed: 0, stale: 0 };
  for (const loc of locations) {
    const s = loc.assignment?.status ?? 'unchanged';
    counts[s] = (counts[s] ?? 0) + 1;
  }
  return STATUSES.map((s) => ({ status: s, count: counts[s] ?? 0 }));
});
