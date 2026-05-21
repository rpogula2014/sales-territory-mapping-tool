import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Store } from '@ngrx/store';

import { FilterDescriptor, FilterValue } from '../../../core/models/live.model';
import {
  LiveActions,
  selectActiveFilters,
  selectFilteredLocations,
  selectFilterSchema,
  selectLoadingFilterSchema,
  selectLocations
} from '../../../store/live';

@Component({
  selector: 'atd-live-filter-sidebar',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './live-filter-sidebar.component.html',
  styleUrl: './live-filter-sidebar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveFilterSidebarComponent {
  private readonly store = inject(Store);

  readonly schema = this.store.selectSignal(selectFilterSchema);
  readonly activeFilters = this.store.selectSignal(selectActiveFilters);
  readonly loading = this.store.selectSignal(selectLoadingFilterSchema);
  readonly totalCount = this.store.selectSignal(selectLocations);
  readonly filteredCount = this.store.selectSignal(selectFilteredLocations);
  readonly activeCount = computed(
    () => Object.values(this.activeFilters()).filter((v) => v != null).length
  );

  private readonly collapsed = signal<Set<string>>(new Set());
  readonly allCollapsed = computed(
    () => this.schema().length > 0 && this.collapsed().size === this.schema().length
  );

  isCollapsed(field: string): boolean {
    return this.collapsed().has(field);
  }

  toggleCollapsed(field: string): void {
    this.collapsed.update((s) => {
      const next = new Set(s);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  }

  toggleAll(): void {
    this.collapsed.update((s) => {
      if (s.size === this.schema().length) return new Set();
      return new Set(this.schema().map((d) => d.field));
    });
  }

  setFilter(field: string, value: FilterValue): void {
    this.store.dispatch(LiveActions.setFilter({ field, value }));
  }

  clearAll(): void {
    this.store.dispatch(LiveActions.clearFilters());
  }

  // --- typed accessors used by template ---

  toggleValue(field: string): boolean | null {
    const v = this.activeFilters()[field];
    return typeof v === 'boolean' ? v : null;
  }

  rangeValue(field: string, desc: FilterDescriptor): [number, number] {
    const v = this.activeFilters()[field];
    if (Array.isArray(v) && v.length === 2 && typeof v[0] === 'number') {
      return v as [number, number];
    }
    return [desc.min ?? 0, desc.max ?? 0];
  }

  multiselectValue(field: string): string[] {
    const v = this.activeFilters()[field];
    return Array.isArray(v) ? (v as string[]) : [];
  }

  textValue(field: string): string {
    const v = this.activeFilters()[field];
    return typeof v === 'string' ? v : '';
  }

  // --- input handlers ---

  onToggleClick(field: string): void {
    const current = this.toggleValue(field);
    const next: FilterValue = current === null ? true : current ? false : null;
    this.setFilter(field, next);
  }

  onRangeMin(field: string, desc: FilterDescriptor, event: Event): void {
    const min = Number((event.target as HTMLInputElement).value);
    const [, max] = this.rangeValue(field, desc);
    this.setFilter(field, [min, max]);
  }

  onRangeMax(field: string, desc: FilterDescriptor, event: Event): void {
    const max = Number((event.target as HTMLInputElement).value);
    const [min] = this.rangeValue(field, desc);
    this.setFilter(field, [min, max]);
  }

  toggleMultiselect(field: string, value: string): void {
    const current = this.multiselectValue(field);
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    this.setFilter(field, next.length ? next : null);
  }

  onText(field: string, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.setFilter(field, value.trim() ? value : null);
  }

  isSelected(field: string, value: string): boolean {
    return this.multiselectValue(field).includes(value);
  }

  isActive(field: string): boolean {
    const v = this.activeFilters()[field];
    if (v == null) return false;
    if (Array.isArray(v) && v.length === 0) return false;
    if (typeof v === 'string' && v.trim() === '') return false;
    return true;
  }

  toggleLabel(field: string): string {
    const v = this.toggleValue(field);
    if (v === null) return 'Any';
    return v ? 'Yes' : 'No';
  }
}
