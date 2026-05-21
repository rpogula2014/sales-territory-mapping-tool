import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Dataset, ImportAccepted, ImportStatus } from '../models/dataset.model';

@Injectable({ providedIn: 'root' })
export class DatasetApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/datasets`;

  list(marketId?: string): Observable<Dataset[]> {
    let params = new HttpParams();
    if (marketId) params = params.set('market_id', marketId);
    return this.http.get<Dataset[]>(this.base, { params });
  }

  import(file: File, marketId: string, datasetName: string): Observable<ImportAccepted> {
    const body = new FormData();
    body.set('file', file);
    body.set('marketId', marketId);
    body.set('datasetName', datasetName);
    return this.http.post<ImportAccepted>(`${this.base}/import`, body);
  }

  importStatus(datasetId: string): Observable<ImportStatus> {
    return this.http.get<ImportStatus>(`${this.base}/${datasetId}/import-status`);
  }

  softDelete(datasetId: string): Observable<{ id: string; deleted_at: string }> {
    return this.http.delete<{ id: string; deleted_at: string }>(`${this.base}/${datasetId}`);
  }

  exportUrl(datasetId: string, params: Record<string, string>): string {
    const search = new URLSearchParams(params).toString();
    return `${this.base}/${datasetId}/export${search ? `?${search}` : ''}`;
  }
}
