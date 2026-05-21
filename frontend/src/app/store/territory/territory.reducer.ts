import { createFeature, createReducer, createSelector, on } from '@ngrx/store';

import { EMPTY_FILTERS, MapFilters } from '../../core/models/map-filters.model';
import { Seller } from '../../core/models/seller.model';
import { TerritoryActions } from './territory.actions';

export interface TerritoryState {
  datasetId: string | null;
  sellers: Seller[];
  filters: MapFilters;
  accounts: GeoJSON.FeatureCollection | null;
  loadingAccounts: boolean;
  selectionIds: string[];
  assignmentSellerId: string;
  saving: boolean;
  statusMessage: string;
}

const initialState: TerritoryState = {
  datasetId: null,
  sellers: [],
  filters: { ...EMPTY_FILTERS },
  accounts: null,
  loadingAccounts: false,
  selectionIds: [],
  assignmentSellerId: '',
  saving: false,
  statusMessage: ''
};

export const territoryFeature = createFeature({
  name: 'territory',
  reducer: createReducer(
    initialState,
    on(TerritoryActions.openDataset, (state, { datasetId }) => ({
      ...initialState,
      datasetId
    })),
    on(TerritoryActions.closeDataset, () => initialState),

    on(TerritoryActions.loadSellersSuccess, (state, { sellers }) => ({ ...state, sellers })),

    on(TerritoryActions.updateFilters, (state, { filters }) => ({
      ...state,
      filters: { ...state.filters, ...filters }
    })),
    on(TerritoryActions.clearFilters, (state) => ({ ...state, filters: { ...EMPTY_FILTERS } })),

    on(TerritoryActions.loadAccounts, (state) => ({ ...state, loadingAccounts: true })),
    on(TerritoryActions.loadAccountsSuccess, (state, { data }) => ({
      ...state,
      accounts: data,
      loadingAccounts: false,
      selectionIds: [],
      assignmentSellerId: ''
    })),
    on(TerritoryActions.loadAccountsFailure, (state, { error }) => ({
      ...state,
      loadingAccounts: false,
      statusMessage: error
    })),

    on(TerritoryActions.setSelection, (state, { accountIds }) => ({
      ...state,
      selectionIds: accountIds,
      assignmentSellerId: firstSellerIdForSelection(state.accounts, accountIds),
      statusMessage: accountIds.length
        ? `${accountIds.length} account(s) selected.`
        : 'No pins selected.'
    })),
    on(TerritoryActions.clearSelection, (state) => ({
      ...state,
      selectionIds: [],
      assignmentSellerId: ''
    })),

    on(TerritoryActions.setAssignmentSeller, (state, { sellerId }) => ({
      ...state,
      assignmentSellerId: sellerId
    })),

    on(TerritoryActions.saveSingleAssignment, TerritoryActions.saveBulkAssignment, (state) => ({
      ...state,
      saving: true,
      statusMessage: 'Saving assignment...'
    })),
    on(TerritoryActions.saveSingleSuccess, (state) => ({
      ...state,
      saving: false,
      statusMessage: 'Assignment saved.'
    })),
    on(TerritoryActions.saveBulkSuccess, (state, { result }) => ({
      ...state,
      saving: false,
      statusMessage: `${result.updatedCount} assignments saved.`
    })),
    on(TerritoryActions.saveAssignmentConflict, (state, { message }) => ({
      ...state,
      saving: false,
      statusMessage: message
    })),
    on(TerritoryActions.saveAssignmentFailure, (state, { error }) => ({
      ...state,
      saving: false,
      statusMessage: error
    }))
  )
});

function firstSellerIdForSelection(
  accounts: GeoJSON.FeatureCollection | null,
  ids: string[]
): string {
  if (!accounts || ids.length === 0) return '';
  const first = accounts.features.find((f) => String(f.properties?.['id']) === ids[0]);
  return String(first?.properties?.['sellerId'] ?? '');
}

export const {
  name: territoryFeatureKey,
  reducer: territoryReducer,
  selectDatasetId,
  selectSellers,
  selectFilters,
  selectAccounts,
  selectLoadingAccounts,
  selectSelectionIds,
  selectAssignmentSellerId,
  selectSaving,
  selectStatusMessage
} = territoryFeature;

export const selectSelectedFeatures = createSelector(
  selectAccounts,
  selectSelectionIds,
  (accounts, ids) => {
    if (!accounts) return [];
    const set = new Set(ids);
    return accounts.features.filter((f) => set.has(String(f.properties?.['id'])));
  }
);

export const selectFirstSelected = createSelector(
  selectSelectedFeatures,
  (features) => features[0] ?? null
);

export const selectTotalCount = createSelector(
  selectAccounts,
  (accounts) => accounts?.features.length ?? 0
);
