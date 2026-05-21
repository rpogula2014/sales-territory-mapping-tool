import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { Seller } from '../../../../core/models/seller.model';

interface SummaryRow {
  sellerId: string;
  displayName: string;
  color: string;
  count: number;
  ttmTotal: number;
}

@Component({
  selector: 'atd-map-seller-summary',
  standalone: true,
  templateUrl: './map-seller-summary.component.html',
  styleUrl: './map-seller-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MapSellerSummaryComponent {
  features = input<GeoJSON.Feature[]>([]);
  sellers = input<Seller[]>([]);

  readonly rows = computed<SummaryRow[]>(() => {
    const byId = new Map<string, SummaryRow>();
    for (const seller of this.sellers()) {
      byId.set(seller.id, {
        sellerId: seller.id,
        displayName: seller.displayName,
        color: seller.color,
        count: 0,
        ttmTotal: 0
      });
    }
    for (const feature of this.features()) {
      const id = String(feature.properties?.['sellerId'] ?? '');
      const ttm = Number(feature.properties?.['ttmVolume'] ?? 0);
      const row =
        byId.get(id) ??
        ({
          sellerId: id,
          displayName: String(feature.properties?.['currentSeller'] ?? 'Unassigned'),
          color: '#7b8794',
          count: 0,
          ttmTotal: 0
        } as SummaryRow);
      row.count += 1;
      row.ttmTotal += Number.isFinite(ttm) ? ttm : 0;
      byId.set(id, row);
    }
    return Array.from(byId.values())
      .filter((row) => row.count > 0)
      .sort((a, b) => b.ttmTotal - a.ttmTotal);
  });

  formatVolume(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(Math.round(n));
  }
}
