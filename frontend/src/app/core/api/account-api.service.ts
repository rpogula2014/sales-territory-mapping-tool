import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AssignmentUpdate, BulkAssignmentResult } from '../models/assignment.model';
import { MapFilters, toFilterParams } from '../models/map-filters.model';

@Injectable({ providedIn: 'root' })
export class AccountApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  geoJson(datasetId: string, filters: MapFilters): Observable<GeoJSON.FeatureCollection> {
    let params = new HttpParams().set('format', 'geojson');
    for (const [key, value] of Object.entries(toFilterParams(filters))) {
      params = params.set(key, value);
    }
    return this.http.get<GeoJSON.FeatureCollection>(
      `${this.base}/datasets/${datasetId}/accounts`,
      { params }
    );
  }

  updateAssignment(
    accountId: string,
    sellerId: string,
    version: number
  ): Observable<AssignmentUpdate> {
    return this.http.patch<AssignmentUpdate>(
      `${this.base}/accounts/${accountId}/assignment`,
      { sellerId, version }
    );
  }

  bulkAssign(
    accounts: Array<{ accountId: string; version: number }>,
    sellerId: string
  ): Observable<BulkAssignmentResult> {
    return this.http.post<BulkAssignmentResult>(
      `${this.base}/accounts/bulk-assignment`,
      { accounts, sellerId }
    );
  }
}
