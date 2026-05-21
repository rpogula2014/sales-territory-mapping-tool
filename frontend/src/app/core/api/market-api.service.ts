import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Market, MarketCreateInput } from '../models/market.model';

@Injectable({ providedIn: 'root' })
export class MarketApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/markets`;

  list(): Observable<Market[]> {
    return this.http.get<Market[]>(this.base);
  }

  create(input: MarketCreateInput): Observable<Market> {
    return this.http.post<Market>(this.base, input);
  }

  softDelete(id: string): Observable<Market> {
    return this.http.delete<Market>(`${this.base}/${id}`);
  }
}
