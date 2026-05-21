import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';

import { Dataset } from '../../../core/models/dataset.model';
import { Market } from '../../../core/models/market.model';
import {
  DatasetsActions,
  selectDatasetRemoveMessage,
  selectDatasetRemovingId,
  selectDatasets,
  selectDatasetsLoading
} from '../../../store/datasets';
import { MarketsActions, selectMarkets } from '../../../store/markets';

interface MarketGroup {
  market: Market | { id: string; name: string };
  datasets: Dataset[];
}

@Component({
  selector: 'atd-market-picker-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './market-picker-page.component.html',
  styleUrl: './market-picker-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MarketPickerPageComponent {
  private readonly store = inject(Store);

  readonly markets = this.store.selectSignal(selectMarkets);
  readonly datasets = this.store.selectSignal(selectDatasets);
  readonly loading = this.store.selectSignal(selectDatasetsLoading);
  readonly removingId = this.store.selectSignal(selectDatasetRemovingId);
  readonly removeMessage = this.store.selectSignal(selectDatasetRemoveMessage);

  readonly confirmId = signal<string | null>(null);

  readonly groups = computed<MarketGroup[]>(() => {
    const markets = this.markets();
    const datasets = this.datasets();
    const byMarket = new Map<string, Dataset[]>();
    for (const ds of datasets) {
      const list = byMarket.get(ds.market_id) ?? [];
      list.push(ds);
      byMarket.set(ds.market_id, list);
    }
    return markets.map((market) => ({
      market,
      datasets: byMarket.get(market.id) ?? []
    }));
  });

  constructor() {
    this.store.dispatch(MarketsActions.load());
    this.store.dispatch(DatasetsActions.load({}));
  }

  askConfirm(event: Event, dataset: Dataset): void {
    event.preventDefault();
    event.stopPropagation();
    this.confirmId.set(dataset.id);
  }

  cancelConfirm(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.confirmId.set(null);
  }

  confirmRemove(event: Event, dataset: Dataset): void {
    event.preventDefault();
    event.stopPropagation();
    this.store.dispatch(DatasetsActions.remove({ id: dataset.id }));
    this.confirmId.set(null);
  }

  isConfirming(dataset: Dataset): boolean {
    return this.confirmId() === dataset.id;
  }

  isRemoving(dataset: Dataset): boolean {
    return this.removingId() === dataset.id;
  }
}
