import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { MapFilters } from '../../../../core/models/map-filters.model';
import { Seller } from '../../../../core/models/seller.model';

@Component({
  selector: 'atd-map-filters',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './map-filters.component.html',
  styleUrl: './map-filters.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MapFiltersComponent {
  filters = input.required<MapFilters>();
  sellers = input<Seller[]>([]);
  primaryPrograms = input<string[]>([]);
  secondaryPrograms = input<string[]>([]);
  dcs = input<string[]>([]);

  filtersChange = output<Partial<MapFilters>>();
  cleared = output<void>();

  readonly hasActive = computed(() => Object.values(this.filters()).some((v) => v !== undefined && v !== ''));

  update<K extends keyof MapFilters>(key: K, value: MapFilters[K] | string | null | undefined): void {
    const next: Partial<MapFilters> = {};
    if (value === '' || value === null || value === undefined) {
      next[key] = undefined as MapFilters[K];
    } else {
      next[key] = value as MapFilters[K];
    }
    this.filtersChange.emit(next);
  }

  updateNumber(key: 'ttmMin' | 'ttmMax', event: Event): void {
    const raw = (event.target as HTMLInputElement).value;
    const parsed = raw === '' ? undefined : Number(raw);
    this.update(key, Number.isFinite(parsed) ? parsed : undefined);
  }

  updateString<K extends keyof MapFilters>(key: K, event: Event): void {
    const raw = (event.target as HTMLInputElement | HTMLSelectElement).value;
    this.update(key, raw as MapFilters[K]);
  }

  toggle(key: 'tirePros' | 'activate', event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.update(key, checked || undefined);
  }

  clearAll(): void {
    this.cleared.emit();
  }
}
