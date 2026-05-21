import { createActionGroup, emptyProps, props } from '@ngrx/store';

import { Dataset, ImportAccepted, ImportStatus } from '../../core/models/dataset.model';

export const DatasetsActions = createActionGroup({
  source: 'Datasets',
  events: {
    Load: props<{ marketId?: string }>(),
    'Load Success': props<{ datasets: Dataset[] }>(),
    'Load Failure': props<{ error: string }>(),

    'Import Requested': props<{ file: File; marketId: string; datasetName: string }>(),
    'Import Accepted': props<{ accepted: ImportAccepted }>(),
    'Import Failed': props<{ error: string }>(),

    'Poll Status': props<{ datasetId: string }>(),
    'Status Updated': props<{ status: ImportStatus }>(),
    'Status Polling Stopped': emptyProps(),

    Remove: props<{ id: string }>(),
    'Remove Success': props<{ id: string }>(),
    'Remove Failure': props<{ error: string }>()
  }
});
