import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';

import { LiveDc } from '../../../core/models/live.model';
import {
  LiveActions,
  selectDcs,
  selectLiveError,
  selectLiveMarkets,
  selectLoadingDcs,
  selectLoadingMarkets,
  selectLoadingRegions,
  selectRegions,
  selectSelectedMarket,
  selectSelectedRegion
} from '../../../store/live';

@Component({
  selector: 'atd-live-dc-picker-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './live-dc-picker-page.component.html',
  styleUrl: './live-dc-picker-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveDcPickerPageComponent {
  private readonly store = inject(Store);

  readonly regions = this.store.selectSignal(selectRegions);
  readonly markets = this.store.selectSignal(selectLiveMarkets);
  readonly dcs = this.store.selectSignal(selectDcs);
  readonly selectedRegion = this.store.selectSignal(selectSelectedRegion);
  readonly selectedMarket = this.store.selectSignal(selectSelectedMarket);
  readonly loadingRegions = this.store.selectSignal(selectLoadingRegions);
  readonly loadingMarkets = this.store.selectSignal(selectLoadingMarkets);
  readonly loadingDcs = this.store.selectSignal(selectLoadingDcs);
  readonly error = this.store.selectSignal(selectLiveError);

  constructor() {
    this.store.dispatch(LiveActions.loadRegions());
    this.store.dispatch(LiveActions.loadDcs({ region: null, market: null }));
  }

  onRegionChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value || null;
    this.store.dispatch(LiveActions.regionSelected({ region: value }));
  }

  onMarketChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value || null;
    this.store.dispatch(LiveActions.marketSelected({ market: value }));
  }

  dcId(dc: LiveDc): number | null {
    const id = dc['dc_id'] ?? dc['dcId'];
    return typeof id === 'number' ? id : id != null ? Number(id) : null;
  }

  dcName(dc: LiveDc): string {
    return String(dc['dc_name'] ?? dc['dcName'] ?? this.dcId(dc) ?? '—');
  }

  dcMarket(dc: LiveDc): string {
    return String(dc['market'] ?? '');
  }

  dcRegion(dc: LiveDc): string {
    return String(dc['region'] ?? '');
  }

  /** Stagger delay (ms) for entrance animation; capped so late tiles don't lag. */
  staggerMs(i: number): number {
    return Math.min(i * 18, 360);
  }
}
