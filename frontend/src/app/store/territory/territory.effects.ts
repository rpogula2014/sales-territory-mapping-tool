import { Injectable, inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { Store } from '@ngrx/store';
import { catchError, map, of, switchMap, withLatestFrom } from 'rxjs';

import { AccountApiService } from '../../core/api/account-api.service';
import { SellerApiService } from '../../core/api/seller-api.service';
import { TerritoryActions } from './territory.actions';
import { selectDatasetId, selectFilters } from './territory.reducer';

@Injectable()
export class TerritoryEffects {
  private readonly actions$ = inject(Actions);
  private readonly store = inject(Store);
  private readonly accounts = inject(AccountApiService);
  private readonly sellers = inject(SellerApiService);

  readonly openDataset$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TerritoryActions.openDataset),
      switchMap(({ datasetId }) => [
        TerritoryActions.loadSellers({ datasetId }),
        TerritoryActions.loadAccounts()
      ])
    )
  );

  readonly loadSellers$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TerritoryActions.loadSellers),
      switchMap(({ datasetId }) =>
        this.sellers.forDataset(datasetId).pipe(
          map((sellers) => TerritoryActions.loadSellersSuccess({ sellers })),
          catchError((err) =>
            of(TerritoryActions.loadSellersFailure({
              error: err?.message ?? 'Failed to load sellers'
            }))
          )
        )
      )
    )
  );

  readonly loadAccounts$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TerritoryActions.loadAccounts, TerritoryActions.updateFilters, TerritoryActions.clearFilters),
      withLatestFrom(this.store.select(selectDatasetId), this.store.select(selectFilters)),
      switchMap(([, datasetId, filters]) => {
        if (!datasetId) return of(TerritoryActions.loadAccountsFailure({ error: 'No dataset' }));
        return this.accounts.geoJson(datasetId, filters).pipe(
          map((data) => TerritoryActions.loadAccountsSuccess({ data })),
          catchError((err) =>
            of(TerritoryActions.loadAccountsFailure({
              error: err?.message ?? 'Failed to load accounts'
            }))
          )
        );
      })
    )
  );

  readonly saveSingle$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TerritoryActions.saveSingleAssignment),
      switchMap(({ accountId, sellerId, version }) =>
        this.accounts.updateAssignment(accountId, sellerId, version).pipe(
          switchMap((update) => [
            TerritoryActions.saveSingleSuccess({ update }),
            TerritoryActions.loadAccounts()
          ]),
          catchError((err: HttpErrorResponse) => this.handleSaveError(err))
        )
      )
    )
  );

  readonly saveBulk$ = createEffect(() =>
    this.actions$.pipe(
      ofType(TerritoryActions.saveBulkAssignment),
      switchMap(({ accounts, sellerId }) =>
        this.accounts.bulkAssign(accounts, sellerId).pipe(
          switchMap((result) => [
            TerritoryActions.saveBulkSuccess({ result }),
            TerritoryActions.loadAccounts()
          ]),
          catchError((err: HttpErrorResponse) => this.handleSaveError(err))
        )
      )
    )
  );

  private handleSaveError(err: HttpErrorResponse) {
    if (err.status === 409) {
      return of(
        TerritoryActions.saveAssignmentConflict({
          message: 'Assignment changed elsewhere. Refreshing.'
        }),
        TerritoryActions.loadAccounts()
      );
    }
    return of(
      TerritoryActions.saveAssignmentFailure({ error: err?.message ?? 'Assignment save failed' })
    );
  }
}
