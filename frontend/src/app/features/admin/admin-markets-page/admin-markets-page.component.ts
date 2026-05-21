import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';

import { Market } from '../../../core/models/market.model';
import {
  MarketsActions,
  selectMarkets,
  selectMarketsLoading,
  selectMarketsMutating,
  selectMarketsMutationMessage
} from '../../../store/markets';

@Component({
  selector: 'atd-admin-markets-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './admin-markets-page.component.html',
  styleUrl: './admin-markets-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminMarketsPageComponent {
  private readonly store = inject(Store);

  readonly markets = this.store.selectSignal(selectMarkets);
  readonly loading = this.store.selectSignal(selectMarketsLoading);
  readonly mutating = this.store.selectSignal(selectMarketsMutating);
  readonly message = this.store.selectSignal(selectMarketsMutationMessage);

  readonly name = signal('');
  readonly region = signal('');
  readonly confirmId = signal<string | null>(null);

  readonly canCreate = computed(() => this.name().trim().length > 0 && !this.mutating());

  constructor() {
    this.store.dispatch(MarketsActions.load());
  }

  setName(value: string): void {
    this.name.set(value);
  }

  setRegion(value: string): void {
    this.region.set(value);
  }

  submit(): void {
    if (!this.canCreate()) return;
    this.store.dispatch(
      MarketsActions.create({
        input: {
          name: this.name().trim(),
          region: this.region().trim() || null
        }
      })
    );
    this.name.set('');
    this.region.set('');
  }

  askConfirm(market: Market): void {
    this.confirmId.set(market.id);
  }

  cancelConfirm(): void {
    this.confirmId.set(null);
  }

  confirmRemove(market: Market): void {
    this.store.dispatch(MarketsActions.remove({ id: market.id }));
    this.confirmId.set(null);
  }

  isConfirming(market: Market): boolean {
    return this.confirmId() === market.id;
  }
}
