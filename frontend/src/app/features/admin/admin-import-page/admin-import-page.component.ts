import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';

import {
  DatasetsActions,
  selectImportError,
  selectImportStatus,
  selectImporting
} from '../../../store/datasets';
import { MarketsActions, selectMarkets } from '../../../store/markets';

@Component({
  selector: 'atd-admin-import-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './admin-import-page.component.html',
  styleUrl: './admin-import-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminImportPageComponent {
  private readonly store = inject(Store);

  readonly markets = this.store.selectSignal(selectMarkets);
  readonly status = this.store.selectSignal(selectImportStatus);
  readonly error = this.store.selectSignal(selectImportError);
  readonly importing = this.store.selectSignal(selectImporting);

  readonly file = signal<File | null>(null);
  readonly datasetName = signal('');
  readonly marketId = signal('');
  readonly validationError = signal('');

  readonly canUpload = computed(
    () => !!this.file() && !!this.marketId() && !!this.datasetName() && !this.importing()
  );

  readonly progressPct = computed(() => {
    const s = this.status();
    if (!s || !s.rowCount) return 0;
    return Math.min(100, Math.round((s.processedCount / s.rowCount) * 100));
  });

  constructor() {
    this.store.dispatch(MarketsActions.load());
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file.set(input.files?.[0] ?? null);
  }

  setName(value: string): void {
    this.datasetName.set(value);
  }

  setMarket(value: string): void {
    this.marketId.set(value);
  }

  upload(): void {
    const file = this.file();
    if (!file || !this.marketId() || !this.datasetName()) {
      this.validationError.set('Choose file, market, and dataset name.');
      return;
    }
    this.validationError.set('');
    this.store.dispatch(
      DatasetsActions.importRequested({
        file,
        marketId: this.marketId(),
        datasetName: this.datasetName()
      })
    );
  }
}
