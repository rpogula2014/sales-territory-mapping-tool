import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { Seller } from '../../../../core/models/seller.model';

@Component({
  selector: 'atd-map-pin-detail',
  standalone: true,
  templateUrl: './map-pin-detail.component.html',
  styleUrl: './map-pin-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MapPinDetailComponent {
  account = input.required<Record<string, unknown>>();
  sellers = input<Seller[]>([]);
  assignmentSellerId = input<string>('');
  saving = input<boolean>(false);

  assignmentSellerIdChange = output<string>();
  save = output<void>();

  onSelect(event: Event): void {
    this.assignmentSellerIdChange.emit((event.target as HTMLSelectElement).value);
  }

  prop(key: string): string {
    const value = this.account()[key];
    return value === null || value === undefined ? '—' : String(value);
  }
}
