import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Seller } from '../models/seller.model';

@Injectable({ providedIn: 'root' })
export class SellerApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  forDataset(datasetId: string): Observable<Seller[]> {
    return this.http.get<Seller[]>(`${this.base}/datasets/${datasetId}/sellers`);
  }
}
