import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { Store } from '@ngrx/store';

import { AssignmentStatus, LiveLocation } from '../../../core/models/live.model';
import { LiveActions, selectLocations, selectSaving } from '../../../store/live';

interface SellerOption {
  id: number;
  name: string;
}

@Component({
  selector: 'atd-live-assign-panel',
  standalone: true,
  templateUrl: './live-assign-panel.component.html',
  styleUrl: './live-assign-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveAssignPanelComponent {
  readonly row = input.required<LiveLocation>();
  readonly dcId = input<number | null>(null);
  readonly dcName = input<string | null>(null);
  readonly market = input<string | null>(null);
  readonly region = input<string | null>(null);
  readonly close = output<void>();

  private readonly store = inject(Store);

  readonly saving = this.store.selectSignal(selectSaving);
  readonly locations = this.store.selectSignal(selectLocations);

  /** Distinct sellers seen in the DC payload — Phase 3 dropdown source. */
  readonly sellerOptions = computed<SellerOption[]>(() => {
    const seen = new Map<number, string>();
    for (const loc of this.locations()) {
      if (loc.primarySalesRepId != null && loc.salesrepName) {
        if (!seen.has(loc.primarySalesRepId)) seen.set(loc.primarySalesRepId, loc.salesrepName);
      }
      const a = loc.assignment;
      if (a?.sellerId != null && a.sellerName && !seen.has(a.sellerId)) {
        seen.set(a.sellerId, a.sellerName);
      }
    }
    return [...seen.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((x, y) => x.name.localeCompare(y.name));
  });

  readonly currentSellerId = computed<number | null>(
    () => this.row().assignment?.sellerId ?? this.row().primarySalesRepId ?? null
  );

  readonly liveSellerId = computed(() => this.row().primarySalesRepId ?? null);
  readonly liveSellerName = computed(() => this.row().salesrepName ?? null);
  readonly status = computed<AssignmentStatus>(() => this.row().assignment?.status ?? 'unchanged');
  readonly hasLocal = computed(() => this.status() !== 'unchanged');

  selectedSellerId: number | null = null;

  ngOnInit(): void {
    this.selectedSellerId = this.currentSellerId();
  }

  onSelect(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedSellerId = value ? Number(value) : null;
  }

  save(): void {
    const id = this.selectedSellerId;
    if (id == null) return;
    const option = this.sellerOptions().find((s) => s.id === id);
    const row = this.row();
    this.store.dispatch(
      LiveActions.saveAssignment({
        siteUseId: row.siteUseID,
        input: {
          sellerId: id,
          sellerName: option?.name ?? null,
          liveSellerId: this.liveSellerId(),
          liveSellerName: this.liveSellerName(),
          expectedVersion: row.assignment?.version ?? 0,
          dcId: this.dcId(),
          dcName: this.dcName(),
          market: this.market(),
          region: this.region(),
          locationNumber: row.locationNumber,
          customerId: row.customerId
        }
      })
    );
  }

  reconfirm(): void {
    const row = this.row();
    const v = row.assignment?.version;
    if (v == null) return;
    this.store.dispatch(
      LiveActions.reconfirmAssignment({
        siteUseId: row.siteUseID,
        liveSellerId: this.liveSellerId(),
        liveSellerName: this.liveSellerName(),
        expectedVersion: v
      })
    );
  }

  acceptSource(): void {
    const row = this.row();
    const v = row.assignment?.version;
    if (v == null) return;
    this.store.dispatch(
      LiveActions.revertAssignment({ siteUseId: row.siteUseID, expectedVersion: v })
    );
  }

  onClose(): void {
    this.close.emit();
  }
}
