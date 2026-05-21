import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

import { LiveApiService } from '../../../core/api/live-api.service';
import { LiveLocation } from '../../../core/models/live.model';
import {
  LiveActions,
  selectDcs,
  selectFilteredLocations,
  selectLiveError,
  selectLoadingLocations,
  selectLocations,
  selectSaveMessage,
  selectStatusCounts,
  selectStatusFilter
} from '../../../store/live';
import { LiveFilterSidebarComponent } from '../live-filter-sidebar/live-filter-sidebar.component';
import { LiveAssignPanelComponent } from '../live-assign-panel/live-assign-panel.component';

type SortKey = keyof LiveLocation;

const CURRENCY = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0
});

@Component({
  selector: 'atd-live-locations-page',
  standalone: true,
  imports: [RouterLink, LiveFilterSidebarComponent, LiveAssignPanelComponent],
  templateUrl: './live-locations-page.component.html',
  styleUrl: './live-locations-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveLocationsPageComponent {
  private readonly store = inject(Store);
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(LiveApiService);

  readonly dcId = toSignal(
    this.route.paramMap.pipe(map((p) => Number(p.get('dcId')))),
    { initialValue: 0 }
  );

  readonly locations = this.store.selectSignal(selectLocations);
  readonly dcs = this.store.selectSignal(selectDcs);
  readonly currentDc = computed(() => {
    const id = this.dcId();
    return this.dcs().find((d) => d.dc_id === id) ?? null;
  });
  readonly filtered = this.store.selectSignal(selectFilteredLocations);
  readonly loading = this.store.selectSignal(selectLoadingLocations);
  readonly error = this.store.selectSignal(selectLiveError);
  readonly statusCounts = this.store.selectSignal(selectStatusCounts);
  readonly statusFilter = this.store.selectSignal(selectStatusFilter);
  readonly saveMessage = this.store.selectSignal(selectSaveMessage);

  readonly sortKey = signal<SortKey>('locationNumber');
  readonly sortAsc = signal(true);
  readonly query = signal('');
  readonly selectedSiteUseID = signal<string | null>(null);
  readonly pageSize = signal(50);
  readonly pageIndex = signal(0);
  readonly bulkSelected = signal<Set<string>>(new Set());
  readonly bulkSellerId = signal<number | null>(null);
  readonly bulkSaving = signal(false);
  readonly showStatusHelp = signal(false);
  readonly coordsFilter = signal<'all' | 'mapped' | 'missing'>('all');

  readonly coordsCounts = computed(() => {
    const rows = this.filtered();
    let mapped = 0;
    let missing = 0;
    for (const r of rows) {
      if (r.latitude != null && r.longitude != null) mapped++;
      else missing++;
    }
    return { all: rows.length, mapped, missing };
  });

  setCoordsFilter(value: 'all' | 'mapped' | 'missing'): void {
    this.coordsFilter.set(value);
    this.pageIndex.set(0);
  }

  toggleStatusHelp(): void {
    this.showStatusHelp.update((v) => !v);
  }

  readonly sellerOptions = computed(() => {
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

  readonly selectedRow = computed<LiveLocation | null>(() => {
    const id = this.selectedSiteUseID();
    if (!id) return null;
    return this.locations().find((r) => r.siteUseID === id) ?? null;
  });

  readonly sorted = computed<LiveLocation[]>(() => {
    const q = this.query().trim().toLowerCase();
    const key = this.sortKey();
    const asc = this.sortAsc();
    const coords = this.coordsFilter();
    let base = this.filtered();
    if (coords === 'mapped') {
      base = base.filter((r) => r.latitude != null && r.longitude != null);
    } else if (coords === 'missing') {
      base = base.filter((r) => r.latitude == null || r.longitude == null);
    }
    const list = q
      ? base.filter((r) =>
          Object.values(r).some((v) => String(v ?? '').toLowerCase().includes(q))
        )
      : [...base];
    list.sort((a, b) => {
      const av = a[key] ?? '';
      const bv = b[key] ?? '';
      if (av === bv) return 0;
      return (av > bv ? 1 : -1) * (asc ? 1 : -1);
    });
    return list;
  });

  readonly pageCount = computed(() => Math.max(1, Math.ceil(this.sorted().length / this.pageSize())));

  readonly view = computed<LiveLocation[]>(() => {
    const list = this.sorted();
    const size = this.pageSize();
    const start = this.pageIndex() * size;
    return list.slice(start, start + size);
  });

  readonly pageStart = computed(() =>
    this.sorted().length === 0 ? 0 : this.pageIndex() * this.pageSize() + 1
  );

  readonly pageEnd = computed(() =>
    Math.min((this.pageIndex() + 1) * this.pageSize(), this.sorted().length)
  );


  constructor() {
    const id = this.dcId();
    if (id) this.store.dispatch(LiveActions.loadLocations({ dcId: id }));

    // Reset page when filters / sort / search / page size change.
    effect(() => {
      this.filtered();
      this.query();
      this.sortKey();
      this.sortAsc();
      this.pageSize();
      this.pageIndex.set(0);
    }, { allowSignalWrites: true });
  }

  sortBy(key: SortKey): void {
    if (this.sortKey() === key) {
      this.sortAsc.update((v) => !v);
    } else {
      this.sortKey.set(key);
      this.sortAsc.set(true);
    }
  }

  onSearch(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  selectRow(row: LiveLocation): void {
    this.selectedSiteUseID.set(row.siteUseID);
  }

  closePanel(): void {
    this.selectedSiteUseID.set(null);
  }

  toggleStatus(status: string): void {
    const current = this.statusFilter();
    const next = current.includes(status)
      ? current.filter((s) => s !== status)
      : [...current, status];
    this.store.dispatch(LiveActions.setStatusFilter({ statuses: next }));
  }

  isStatusActive(status: string): boolean {
    return this.statusFilter().includes(status);
  }

  currency(value: number | null | undefined): string {
    if (value == null || Number.isNaN(value)) return '—';
    return CURRENCY.format(value);
  }

  yoyDelta(row: LiveLocation): number {
    const ytd = row.ytdsales ?? 0;
    const prior = row.priorytdsales ?? 0;
    if (!prior) return 0;
    return (ytd - prior) / prior;
  }

  yoyPct(row: LiveLocation): string {
    if (row.ytdsales == null || row.priorytdsales == null || !row.priorytdsales) return '—';
    const pct = this.yoyDelta(row) * 100;
    const sign = pct >= 0 ? '+' : '';
    return `${sign}${pct.toFixed(1)}%`;
  }

  // === bulk ===

  toggleBulk(row: LiveLocation, event: Event): void {
    event.stopPropagation();
    const id = row.siteUseID;
    this.bulkSelected.update((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  toggleBulkAll(): void {
    const rows = this.view();
    if (this.bulkSelected().size === rows.length) {
      this.bulkSelected.set(new Set());
    } else {
      this.bulkSelected.set(new Set(rows.map((r) => r.siteUseID)));
    }
  }

  isBulkSelected(row: LiveLocation): boolean {
    return this.bulkSelected().has(row.siteUseID);
  }

  bulkCount(): number {
    return this.bulkSelected().size;
  }

  onBulkSellerChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.bulkSellerId.set(value ? Number(value) : null);
  }

  prevPage(): void {
    this.pageIndex.update((i) => Math.max(0, i - 1));
  }

  nextPage(): void {
    this.pageIndex.update((i) => Math.min(this.pageCount() - 1, i + 1));
  }

  goToPage(p: number): void {
    this.pageIndex.set(Math.max(0, Math.min(this.pageCount() - 1, p)));
  }

  onPageSize(event: Event): void {
    this.pageSize.set(Number((event.target as HTMLSelectElement).value));
  }

  applyBulk(): void {
    const sellerId = this.bulkSellerId();
    const ids = [...this.bulkSelected()];
    if (sellerId == null || ids.length === 0) return;
    const seller = this.sellerOptions().find((s) => s.id === sellerId);
    const liveBySite: Record<string, Record<string, unknown>> = {};
    const expectedVersions: Record<string, number> = {};
    const byId = new Map(this.locations().map((l) => [l.siteUseID, l]));
    for (const id of ids) {
      const loc = byId.get(id);
      if (!loc) continue;
      liveBySite[id] = {
        liveSellerId: loc.primarySalesRepId,
        liveSellerName: loc.salesrepName,
        locationNumber: loc.locationNumber,
        customerId: loc.customerId
      };
      expectedVersions[id] = loc.assignment?.version ?? 0;
    }
    this.bulkSaving.set(true);
    this.api
      .bulkAssign({
        siteUseIds: ids,
        sellerId,
        sellerName: seller?.name ?? null,
        dcId: this.dcId(),
        dcName: (this.currentDc()?.dc_name as string | undefined) ?? null,
        market: (this.currentDc()?.market as string | undefined) ?? null,
        region: (this.currentDc()?.region as string | undefined) ?? null,
        liveBySite,
        expectedVersions
      })
      .subscribe({
        next: (res) => {
          if (res.conflicts.length > 0) {
            this.bulkSelected.set(new Set(res.conflicts.map((c) => c.siteUseId)));
            alert(
              `${res.ok.length} updated. ${res.conflicts.length} skipped — version changed by another user. Reload, review, retry.`
            );
          } else {
            this.bulkSelected.set(new Set());
          }
          this.bulkSellerId.set(null);
          this.bulkSaving.set(false);
          this.store.dispatch(LiveActions.loadLocations({ dcId: this.dcId() }));
        },
        error: () => this.bulkSaving.set(false)
      });
  }
}
