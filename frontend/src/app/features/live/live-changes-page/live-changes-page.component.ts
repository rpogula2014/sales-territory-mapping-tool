import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LiveApiService } from '../../../core/api/live-api.service';
import {
  ChangeRow,
  ChangesPage,
  ChangesSummary
} from '../../../core/models/live.model';

@Component({
  selector: 'atd-live-changes-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './live-changes-page.component.html',
  styleUrl: './live-changes-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveChangesPageComponent {
  private readonly api = inject(LiveApiService);

  readonly page = signal<ChangesPage | null>(null);
  readonly summary = signal<ChangesSummary | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly selected = signal<Set<string>>(new Set());

  // Filter form (simple — power-user filters tracked in signals).
  readonly fRegion = signal('');
  readonly fMarket = signal('');
  readonly fDc = signal('');
  readonly fAssignedBy = signal('');
  readonly fOnlyChanged = signal(false);

  readonly selectedCount = computed(() => this.selected().size);
  readonly showStatusHelp = signal(false);

  toggleStatusHelp(): void {
    this.showStatusHelp.update((v) => !v);
  }

  /** Distinct DCs surfaced from the loaded rows, sorted by name. */
  readonly dcOptions = computed(() => {
    const rows = this.page()?.rows ?? [];
    const seen = new Map<number, string>();
    for (const r of rows) {
      if (r.dcId != null && !seen.has(r.dcId)) {
        seen.set(r.dcId, r.dcName ?? '');
      }
    }
    return [...seen.entries()]
      .map(([dcId, dcName]) => ({ dcId, dcName: dcName || `Unknown DC` }))
      .sort((a, b) => a.dcName.localeCompare(b.dcName));
  });

  constructor() {
    this.reload();
  }

  reload(preserveSelection = false): void {
    this.loading.set(true);
    this.error.set(null);
    if (!preserveSelection) this.selected.set(new Set());

    const params: Record<string, string | number | boolean> = {};
    if (this.fRegion()) params['region'] = this.fRegion();
    if (this.fMarket()) params['market'] = this.fMarket();
    if (this.fDc()) params['dcId'] = Number(this.fDc());
    if (this.fAssignedBy()) params['assignedBy'] = this.fAssignedBy();
    if (this.fOnlyChanged()) params['onlyChanged'] = true;

    this.api.changes(params).subscribe({
      next: (page) => {
        this.page.set(page);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? err?.message ?? 'Failed to load changes');
        this.loading.set(false);
      }
    });

    this.api.changesSummary().subscribe({
      next: (summary) => this.summary.set(summary),
      error: () => undefined
    });
  }

  toggleAll(rows: ChangeRow[]): void {
    const current = this.selected();
    if (current.size === rows.length) {
      this.selected.set(new Set());
    } else {
      this.selected.set(new Set(rows.map((r) => r.siteUseID)));
    }
  }

  toggleOne(siteUseID: string): void {
    this.selected.update((s) => {
      const next = new Set(s);
      if (next.has(siteUseID)) next.delete(siteUseID);
      else next.add(siteUseID);
      return next;
    });
  }

  isSelected(siteUseID: string): boolean {
    return this.selected().has(siteUseID);
  }

  bulkRevert(): void {
    const ids = [...this.selected()];
    if (ids.length === 0) return;
    if (!confirm(`Accept source for ${ids.length} location(s)? Local assignments will be cleared.`)) return;
    const rowsById = new Map((this.page()?.rows ?? []).map((r) => [r.siteUseID, r]));
    const expectedVersions: Record<string, number> = {};
    for (const id of ids) {
      const row = rowsById.get(id);
      if (row) expectedVersions[id] = row.version;
    }
    this.loading.set(true);
    this.api.bulkRevert(ids, expectedVersions).subscribe({
      next: (res) => {
        const hasConflicts = res.conflicts.length > 0;
        if (hasConflicts) {
          this.message.set(
            `Reverted ${res.ok.length}. ${res.conflicts.length} skipped — version changed by another user.`
          );
          this.selected.set(new Set(res.conflicts.map((c) => c.siteUseId)));
        } else {
          this.message.set(`Reverted ${res.ok.length} assignment(s).`);
        }
        this.reload(hasConflicts);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? err?.message ?? 'Bulk revert failed');
        this.loading.set(false);
      }
    });
  }

  setRegion(event: Event): void { this.fRegion.set((event.target as HTMLInputElement).value); }
  setMarket(event: Event): void { this.fMarket.set((event.target as HTMLInputElement).value); }
  setDc(event: Event): void { this.fDc.set((event.target as HTMLSelectElement).value); }
  setAssignedBy(event: Event): void { this.fAssignedBy.set((event.target as HTMLInputElement).value); }
  setOnlyChanged(event: Event): void {
    this.fOnlyChanged.set((event.target as HTMLInputElement).checked);
  }

  exportCsv(): void {
    const params: Record<string, string | number | boolean> = {};
    if (this.fRegion()) params['region'] = this.fRegion();
    if (this.fMarket()) params['market'] = this.fMarket();
    if (this.fDc()) params['dcId'] = Number(this.fDc());
    if (this.fAssignedBy()) params['assignedBy'] = this.fAssignedBy();
    if (this.fOnlyChanged()) params['onlyChanged'] = true;
    const url = this.api.changesCsvUrl(params);
    window.location.href = url;
  }
}
