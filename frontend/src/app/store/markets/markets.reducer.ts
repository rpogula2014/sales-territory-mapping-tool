import { createFeature, createReducer, on } from '@ngrx/store';

import { Market } from '../../core/models/market.model';
import { MarketsActions } from './markets.actions';

export interface MarketsState {
  items: Market[];
  loading: boolean;
  error: string | null;
  mutating: boolean;
  mutationMessage: string;
}

const initialState: MarketsState = {
  items: [],
  loading: false,
  error: null,
  mutating: false,
  mutationMessage: ''
};

export const marketsFeature = createFeature({
  name: 'markets',
  reducer: createReducer(
    initialState,
    on(MarketsActions.load, (state) => ({ ...state, loading: true, error: null })),
    on(MarketsActions.loadSuccess, (state, { markets }) => ({
      ...state,
      items: markets,
      loading: false
    })),
    on(MarketsActions.loadFailure, (state, { error }) => ({
      ...state,
      loading: false,
      error
    })),
    on(MarketsActions.create, MarketsActions.remove, (state) => ({
      ...state,
      mutating: true,
      mutationMessage: ''
    })),
    on(MarketsActions.createSuccess, (state, { market }) => ({
      ...state,
      mutating: false,
      mutationMessage: `Created "${market.name}".`,
      items: upsert(state.items, market)
    })),
    on(MarketsActions.removeSuccess, (state, { id }) => ({
      ...state,
      mutating: false,
      mutationMessage: 'Market removed.',
      items: state.items.filter((m) => m.id !== id)
    })),
    on(MarketsActions.createFailure, MarketsActions.removeFailure, (state, { error }) => ({
      ...state,
      mutating: false,
      mutationMessage: error
    }))
  )
});

function upsert(list: Market[], market: Market): Market[] {
  const idx = list.findIndex((m) => m.id === market.id);
  if (idx === -1) return [...list, market].sort((a, b) => a.name.localeCompare(b.name));
  const next = [...list];
  next[idx] = market;
  return next;
}

export const {
  name: marketsFeatureKey,
  reducer: marketsReducer,
  selectItems: selectMarkets,
  selectLoading: selectMarketsLoading,
  selectError: selectMarketsError,
  selectMutating: selectMarketsMutating,
  selectMutationMessage: selectMarketsMutationMessage
} = marketsFeature;
