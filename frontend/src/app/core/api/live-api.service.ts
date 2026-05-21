import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AssignmentBlock,
  AssignmentPatchInput,
  BulkAssignInput,
  BulkResult,
  ChangesPage,
  ChangesSummary,
  FilterDescriptor,
  LiveDc,
  LiveLocation
} from '../models/live.model';

@Injectable({ providedIn: 'root' })
export class LiveApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/live`;

  regions(): Observable<string[]> {
    return this.http.get<string[]>(`${this.base}/regions`);
  }

  markets(region?: string | null): Observable<string[]> {
    let params = new HttpParams();
    if (region) params = params.set('region', region);
    return this.http.get<string[]>(`${this.base}/markets`, { params });
  }

  dcs(region?: string | null, market?: string | null): Observable<LiveDc[]> {
    let params = new HttpParams();
    if (region) params = params.set('region', region);
    if (market) params = params.set('market', market);
    return this.http.get<LiveDc[]>(`${this.base}/dcs`, { params });
  }

  locationsForDc(dcId: number, withMetrics = true): Observable<LiveLocation[]> {
    const params = new HttpParams().set('withMetrics', String(withMetrics));
    return this.http.get<LiveLocation[]>(`${this.base}/dcs/${dcId}/locations`, { params });
  }

  filterSchema(dcId: number): Observable<FilterDescriptor[]> {
    return this.http.get<FilterDescriptor[]>(`${this.base}/dcs/${dcId}/filter-schema`);
  }

  patchAssignment(siteUseId: string, body: AssignmentPatchInput): Observable<AssignmentBlock> {
    return this.http.patch<AssignmentBlock>(
      `${this.base}/locations/${siteUseId}/assignment`,
      body
    );
  }

  revertAssignment(siteUseId: string, expectedVersion: number): Observable<AssignmentBlock> {
    return this.http.request<AssignmentBlock>(
      'DELETE',
      `${this.base}/locations/${siteUseId}/assignment`,
      { body: { expectedVersion } }
    );
  }

  reconfirmAssignment(
    siteUseId: string,
    body: { liveSellerId: number | null; liveSellerName: string | null; expectedVersion: number }
  ): Observable<AssignmentBlock> {
    return this.http.post<AssignmentBlock>(
      `${this.base}/locations/${siteUseId}/reconfirm`,
      body
    );
  }

  changes(params: Record<string, string | number | boolean> = {}): Observable<ChangesPage> {
    let httpParams = new HttpParams();
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') httpParams = httpParams.set(k, String(v));
    }
    return this.http.get<ChangesPage>(`${this.base}/changes`, { params: httpParams });
  }

  changesCsvUrl(params: Record<string, string | number | boolean> = {}): string {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') usp.set(k, String(v));
    }
    const qs = usp.toString();
    return `${this.base}/changes.csv${qs ? `?${qs}` : ''}`;
  }

  changesSummary(): Observable<ChangesSummary> {
    return this.http.get<ChangesSummary>(`${this.base}/changes/summary`);
  }

  bulkAssign(input: BulkAssignInput): Observable<BulkResult> {
    return this.http.post<BulkResult>(`${this.base}/assignments/bulk`, input);
  }

  bulkRevert(
    siteUseIds: string[],
    expectedVersions: Record<string, number> = {}
  ): Observable<BulkResult> {
    return this.http.post<BulkResult>(`${this.base}/changes/bulk-revert`, {
      siteUseIds,
      expectedVersions
    });
  }

  sellerColors(): Observable<Record<string, string>> {
    return this.http.get<Record<string, string>>(`${this.base}/seller-colors`);
  }

  setSellerColor(sellerId: number, color: string): Observable<{ sellerId: string; color: string }> {
    return this.http.put<{ sellerId: string; color: string }>(
      `${this.base}/seller-colors/${sellerId}`,
      { color }
    );
  }

  deleteSellerColor(sellerId: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/seller-colors/${sellerId}`);
  }
}
