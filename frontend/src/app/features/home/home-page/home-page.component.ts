import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { catchError, of } from 'rxjs';

import { LiveApiService } from '../../../core/api/live-api.service';
import { ChangesSummary } from '../../../core/models/live.model';
import { DatasetsActions, selectDatasets } from '../../../store/datasets';
import { MarketsActions, selectMarkets } from '../../../store/markets';

@Component({
  selector: 'atd-home-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './home-page.component.html',
  styleUrl: './home-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HomePageComponent {
  private readonly store = inject(Store);
  private readonly liveApi = inject(LiveApiService);

  readonly markets = this.store.selectSignal(selectMarkets);
  readonly datasets = this.store.selectSignal(selectDatasets);

  readonly activeDatasets = computed(() => this.datasets().filter((d) => d.is_active));
  readonly recentDatasets = computed(() => this.datasets().slice(0, 5));

  private readonly EMPTY_SUMMARY: ChangesSummary = { total: 0, changed: 0, byRegion: [], byDc: [] };

  readonly changesSummary = toSignal(
    this.liveApi.changesSummary().pipe(catchError(() => of(this.EMPTY_SUMMARY))),
    { initialValue: this.EMPTY_SUMMARY }
  );

  constructor() {
    this.store.dispatch(MarketsActions.load());
    this.store.dispatch(DatasetsActions.load({}));
  }
}
