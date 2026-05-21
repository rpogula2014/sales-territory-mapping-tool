import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { Seller } from '../../../../core/models/seller.model';

@Component({
  selector: 'atd-map-bulk-bar',
  standalone: true,
  templateUrl: './map-bulk-bar.component.html',
  styleUrl: './map-bulk-bar.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MapBulkBarComponent {
  selectedCount = input<number>(0);
  sellers = input<Seller[]>([]);
  assignmentSellerId = input<string>('');
  saving = input<boolean>(false);

  assignmentSellerIdChange = output<string>();
  save = output<void>();
  clear = output<void>();

  onSelect(event: Event): void {
    this.assignmentSellerIdChange.emit((event.target as HTMLSelectElement).value);
  }
}
