import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { catchError, interval, map, of, startWith, switchMap, takeWhile } from 'rxjs';

import { DatasetApiService } from '../../core/api/dataset-api.service';
import { DatasetsActions } from './datasets.actions';

@Injectable()
export class DatasetsEffects {
  private readonly actions$ = inject(Actions);
  private readonly api = inject(DatasetApiService);

  readonly load$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DatasetsActions.load),
      switchMap(({ marketId }) =>
        this.api.list(marketId).pipe(
          map((datasets) => DatasetsActions.loadSuccess({ datasets })),
          catchError((err) =>
            of(DatasetsActions.loadFailure({ error: err?.message ?? 'Failed to load datasets' }))
          )
        )
      )
    )
  );

  readonly import$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DatasetsActions.importRequested),
      switchMap(({ file, marketId, datasetName }) =>
        this.api.import(file, marketId, datasetName).pipe(
          map((accepted) => DatasetsActions.importAccepted({ accepted })),
          catchError((err) =>
            of(DatasetsActions.importFailed({ error: err?.message ?? 'Import failed' }))
          )
        )
      )
    )
  );

  readonly remove$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DatasetsActions.remove),
      switchMap(({ id }) =>
        this.api.softDelete(id).pipe(
          map(() => DatasetsActions.removeSuccess({ id })),
          catchError((err) =>
            of(
              DatasetsActions.removeFailure({
                error: err?.error?.detail ?? err?.message ?? 'Failed to remove dataset'
              })
            )
          )
        )
      )
    )
  );

  readonly poll$ = createEffect(() =>
    this.actions$.pipe(
      ofType(DatasetsActions.importAccepted, DatasetsActions.pollStatus),
      switchMap((action) => {
        const datasetId =
          'accepted' in action ? action.accepted.datasetId : action.datasetId;
        return interval(1500).pipe(
          startWith(0),
          switchMap(() => this.api.importStatus(datasetId)),
          takeWhile(
            (status) => status.status === 'queued' || status.status === 'processing',
            true
          ),
          map((status) => DatasetsActions.statusUpdated({ status })),
          catchError((err) =>
            of(DatasetsActions.importFailed({ error: err?.message ?? 'Status poll failed' }))
          )
        );
      })
    )
  );
}
