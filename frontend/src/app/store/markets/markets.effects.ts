import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { catchError, map, of, switchMap } from 'rxjs';

import { MarketApiService } from '../../core/api/market-api.service';
import { MarketsActions } from './markets.actions';

@Injectable()
export class MarketsEffects {
  private readonly actions$ = inject(Actions);
  private readonly api = inject(MarketApiService);

  readonly load$ = createEffect(() =>
    this.actions$.pipe(
      ofType(MarketsActions.load),
      switchMap(() =>
        this.api.list().pipe(
          map((markets) => MarketsActions.loadSuccess({ markets })),
          catchError((err) =>
            of(MarketsActions.loadFailure({ error: err?.message ?? 'Failed to load markets' }))
          )
        )
      )
    )
  );

  readonly create$ = createEffect(() =>
    this.actions$.pipe(
      ofType(MarketsActions.create),
      switchMap(({ input }) =>
        this.api.create(input).pipe(
          map((market) => MarketsActions.createSuccess({ market })),
          catchError((err) =>
            of(
              MarketsActions.createFailure({
                error: err?.error?.detail ?? err?.message ?? 'Failed to create market'
              })
            )
          )
        )
      )
    )
  );

  readonly remove$ = createEffect(() =>
    this.actions$.pipe(
      ofType(MarketsActions.remove),
      switchMap(({ id }) =>
        this.api.softDelete(id).pipe(
          map(() => MarketsActions.removeSuccess({ id })),
          catchError((err) =>
            of(
              MarketsActions.removeFailure({
                error: err?.error?.detail ?? err?.message ?? 'Failed to remove market'
              })
            )
          )
        )
      )
    )
  );
}
