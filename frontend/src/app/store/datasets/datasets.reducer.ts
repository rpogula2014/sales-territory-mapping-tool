import { createFeature, createReducer, on } from '@ngrx/store';

import { Dataset, ImportStatus } from '../../core/models/dataset.model';
import { DatasetsActions } from './datasets.actions';

export interface DatasetsState {
  items: Dataset[];
  loading: boolean;
  error: string | null;
  importStatus: ImportStatus | null;
  importError: string | null;
  importing: boolean;
  removingId: string | null;
  removeMessage: string;
}

const initialState: DatasetsState = {
  items: [],
  loading: false,
  error: null,
  importStatus: null,
  importError: null,
  importing: false,
  removingId: null,
  removeMessage: ''
};

export const datasetsFeature = createFeature({
  name: 'datasets',
  reducer: createReducer(
    initialState,
    on(DatasetsActions.load, (state) => ({ ...state, loading: true, error: null })),
    on(DatasetsActions.loadSuccess, (state, { datasets }) => ({
      ...state,
      items: datasets,
      loading: false
    })),
    on(DatasetsActions.loadFailure, (state, { error }) => ({
      ...state,
      loading: false,
      error
    })),
    on(DatasetsActions.importRequested, (state) => ({
      ...state,
      importing: true,
      importError: null,
      importStatus: null
    })),
    on(DatasetsActions.importAccepted, (state) => ({ ...state, importing: true })),
    on(DatasetsActions.importFailed, (state, { error }) => ({
      ...state,
      importing: false,
      importError: error
    })),
    on(DatasetsActions.statusUpdated, (state, { status }) => ({
      ...state,
      importStatus: status,
      importing: status.status === 'queued' || status.status === 'processing'
    })),
    on(DatasetsActions.statusPollingStopped, (state) => ({ ...state, importing: false })),

    on(DatasetsActions.remove, (state, { id }) => ({
      ...state,
      removingId: id,
      removeMessage: ''
    })),
    on(DatasetsActions.removeSuccess, (state, { id }) => ({
      ...state,
      removingId: null,
      removeMessage: 'Dataset removed.',
      items: state.items.filter((d) => d.id !== id)
    })),
    on(DatasetsActions.removeFailure, (state, { error }) => ({
      ...state,
      removingId: null,
      removeMessage: error
    }))
  )
});

export const {
  name: datasetsFeatureKey,
  reducer: datasetsReducer,
  selectItems: selectDatasets,
  selectLoading: selectDatasetsLoading,
  selectImportStatus,
  selectImportError,
  selectImporting,
  selectRemovingId: selectDatasetRemovingId,
  selectRemoveMessage: selectDatasetRemoveMessage
} = datasetsFeature;
