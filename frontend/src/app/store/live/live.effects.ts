import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { catchError, map, of, switchMap, withLatestFrom } from 'rxjs';

import { LiveApiService } from '../../core/api/live-api.service';
import { LiveActions } from './live.actions';
import { selectSelectedMarket, selectSelectedRegion } from './live.reducer';

function errMsg(err: unknown, fallback: string): string {
  const e = err as { error?: { detail?: string }; message?: string };
  return e?.error?.detail ?? e?.message ?? fallback;
}

@Injectable()
export class LiveEffects {
  private readonly actions$ = inject(Actions);
  private readonly store = inject(Store);
  private readonly api = inject(LiveApiService);

  readonly loadRegions$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadRegions),
      switchMap(() =>
        this.api.regions().pipe(
          map((regions) => LiveActions.loadRegionsSuccess({ regions })),
          catchError((err) =>
            of(LiveActions.loadRegionsFailure({ error: errMsg(err, 'Failed to load regions') }))
          )
        )
      )
    )
  );

  readonly regionSelected$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.regionSelected),
      map(({ region }) => LiveActions.loadMarkets({ region }))
    )
  );

  readonly loadMarkets$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadMarkets),
      switchMap(({ region }) =>
        this.api.markets(region).pipe(
          map((markets) => LiveActions.loadMarketsSuccess({ markets })),
          catchError((err) =>
            of(LiveActions.loadMarketsFailure({ error: errMsg(err, 'Failed to load markets') }))
          )
        )
      )
    )
  );

  readonly marketSelected$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.marketSelected),
      withLatestFrom(this.store.select(selectSelectedRegion)),
      map(([{ market }, region]) => LiveActions.loadDcs({ region, market }))
    )
  );

  readonly regionSelectedReloadDcs$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.regionSelected),
      withLatestFrom(this.store.select(selectSelectedMarket)),
      map(([{ region }, market]) => LiveActions.loadDcs({ region, market }))
    )
  );

  readonly loadDcs$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadDcs),
      switchMap(({ region, market }) =>
        this.api.dcs(region, market).pipe(
          map((dcs) => LiveActions.loadDcsSuccess({ dcs })),
          catchError((err) =>
            of(LiveActions.loadDcsFailure({ error: errMsg(err, 'Failed to load DCs') }))
          )
        )
      )
    )
  );

  readonly loadLocations$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadLocations),
      switchMap(({ dcId }) =>
        this.api.locationsForDc(dcId).pipe(
          map((locations) => LiveActions.loadLocationsSuccess({ locations })),
          catchError((err) =>
            of(LiveActions.loadLocationsFailure({ error: errMsg(err, 'Failed to load locations') }))
          )
        )
      )
    )
  );

  // When locations land for a DC, fetch its filter schema in parallel.
  readonly loadFilterSchemaOnLocations$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadLocations),
      map(({ dcId }) => LiveActions.loadFilterSchema({ dcId }))
    )
  );

  readonly loadFilterSchema$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.loadFilterSchema),
      switchMap(({ dcId }) =>
        this.api.filterSchema(dcId).pipe(
          map((schema) => LiveActions.loadFilterSchemaSuccess({ schema })),
          catchError((err) =>
            of(
              LiveActions.loadFilterSchemaFailure({
                error: errMsg(err, 'Failed to load filter schema')
              })
            )
          )
        )
      )
    )
  );

  readonly saveAssignment$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.saveAssignment),
      switchMap(({ siteUseId, input }) =>
        this.api.patchAssignment(siteUseId, input).pipe(
          map((assignment) =>
            LiveActions.saveAssignmentSuccess({ siteUseId, assignment })
          ),
          catchError((err) =>
            of(
              LiveActions.saveAssignmentFailure({
                error: errMsg(err, 'Failed to save assignment')
              })
            )
          )
        )
      )
    )
  );

  readonly reconfirmAssignment$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.reconfirmAssignment),
      switchMap(({ siteUseId, liveSellerId, liveSellerName, expectedVersion }) =>
        this.api
          .reconfirmAssignment(siteUseId, { liveSellerId, liveSellerName, expectedVersion })
          .pipe(
            map((assignment) =>
              LiveActions.reconfirmAssignmentSuccess({ siteUseId, assignment })
            ),
            catchError((err) =>
              of(
                LiveActions.reconfirmAssignmentFailure({
                  error: errMsg(err, 'Failed to reconfirm assignment')
                })
              )
            )
          )
      )
    )
  );

  readonly revertAssignment$ = createEffect(() =>
    this.actions$.pipe(
      ofType(LiveActions.revertAssignment),
      switchMap(({ siteUseId, expectedVersion }) =>
        this.api.revertAssignment(siteUseId, expectedVersion).pipe(
          map(() => LiveActions.revertAssignmentSuccess({ siteUseId })),
          catchError((err) =>
            of(
              LiveActions.revertAssignmentFailure({
                error: errMsg(err, 'Failed to revert assignment')
              })
            )
          )
        )
      )
    )
  );
}
