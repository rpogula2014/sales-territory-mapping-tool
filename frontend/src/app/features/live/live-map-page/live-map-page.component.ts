import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  ViewChild,
  computed,
  effect,
  inject,
  signal
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import { toSignal } from '@angular/core/rxjs-interop';
import { map as rxMap } from 'rxjs';
import maplibregl, { Map as MapLibreMap, MapMouseEvent, Point } from 'maplibre-gl';

import { environment } from '../../../../environments/environment';
import { LiveApiService } from '../../../core/api/live-api.service';
import { LiveLocation } from '../../../core/models/live.model';
import {
  LiveActions,
  selectDcs,
  selectFilteredLocations,
  selectLiveError,
  selectLoadingLocations,
  selectLocations
} from '../../../store/live';
import { LiveFilterSidebarComponent } from '../live-filter-sidebar/live-filter-sidebar.component';

interface PinFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: {
    siteUseID: string;
    locationNumber: string | null;
    dba_name: string | null;
    salesrepName: string | null;
    lat_source: string;
    selected: boolean;
    color: string;
    sellerKey: string;
  };
}

// 16-step palette; cycle by hashed seller id.
const SELLER_PALETTE = [
  '#0b6bcb', '#1a7f3e', '#b25b00', '#b42318', '#7a3ea1', '#0098a3',
  '#c2410c', '#3f6212', '#5b21b6', '#0e7490', '#a16207', '#9d174d',
  '#1d4ed8', '#15803d', '#ea580c', '#7c2d12'
];

function sellerColor(sellerKey: string, overrides: Record<string, string> = {}): string {
  if (!sellerKey || sellerKey === 'none') return '#9aa3ad';
  const override = overrides[sellerKey];
  if (override) return override;
  let h = 0;
  for (let i = 0; i < sellerKey.length; i++) h = (h * 31 + sellerKey.charCodeAt(i)) >>> 0;
  return SELLER_PALETTE[h % SELLER_PALETTE.length];
}

/** Resolve the seller that drives a pin's color — assigned > live. */
function effectiveSellerKey(r: LiveLocation): string {
  const a = r.assignment;
  if (a?.sellerId != null) return String(a.sellerId);
  if (r.primarySalesRepId != null) return String(r.primarySalesRepId);
  return 'none';
}

function effectiveSellerName(r: LiveLocation): string {
  return r.assignment?.sellerName ?? r.salesrepName ?? 'Unassigned';
}

@Component({
  selector: 'atd-live-map-page',
  standalone: true,
  imports: [RouterLink, LiveFilterSidebarComponent],
  templateUrl: './live-map-page.component.html',
  styleUrl: './live-map-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LiveMapPageComponent implements AfterViewInit {
  @ViewChild('mapContainer', { static: true }) private readonly mapContainer!: ElementRef<HTMLElement>;
  @ViewChild('selectionBox', { static: true }) private readonly selectionBox!: ElementRef<HTMLElement>;

  private readonly store = inject(Store);
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(LiveApiService);
  private readonly destroyRef = inject(DestroyRef);
  private map?: MapLibreMap;
  private dragStart?: Point;

  readonly dcId = toSignal(this.route.paramMap.pipe(rxMap((p) => Number(p.get('dcId')))), {
    initialValue: 0
  });

  readonly locations = this.store.selectSignal(selectLocations);
  readonly dcs = this.store.selectSignal(selectDcs);
  readonly currentDc = computed(() => {
    const id = this.dcId();
    return this.dcs().find((d) => d.dc_id === id) ?? null;
  });
  readonly filtered = this.store.selectSignal(selectFilteredLocations);
  readonly loading = this.store.selectSignal(selectLoadingLocations);
  readonly error = this.store.selectSignal(selectLiveError);
  readonly selected = signal<LiveLocation | null>(null);

  readonly rectangleMode = signal(false);
  readonly bulkSelected = signal<Set<string>>(new Set());
  readonly bulkSellerId = signal<number | null>(null);
  readonly bulkSaving = signal(false);
  readonly customColors = signal<Record<string, string>>({});
  readonly clusterEnabled = signal(true);

  readonly mappable = computed(() => this.filtered().filter(hasCoords));
  readonly unmappableCount = computed(() => this.filtered().length - this.mappable().length);
  readonly censusCount = computed(
    () => this.mappable().filter((r) => r.lat_source === 'census').length
  );

  readonly divergenceCount = computed(
    () =>
      this.mappable().filter((r) => {
        const status = r.assignment?.status;
        return status === 'changed' || status === 'stale';
      }).length
  );

  /** Seller → color legend for visible pins, sorted by count desc. */
  readonly legend = computed<
    { name: string; key: string; color: string; count: number; custom: boolean }[]
  >(() => {
    const counts = new Map<string, { name: string; count: number }>();
    for (const r of this.mappable()) {
      const key = effectiveSellerKey(r);
      const name = effectiveSellerName(r);
      const hit = counts.get(key);
      if (hit) hit.count += 1;
      else counts.set(key, { name, count: 1 });
    }
    const overrides = this.customColors();
    return [...counts.entries()]
      .map(([key, { name, count }]) => ({
        key,
        name,
        color: sellerColor(key, overrides),
        count,
        custom: key in overrides
      }))
      .sort((a, b) => b.count - a.count);
  });

  readonly sellerOptions = computed(() => {
    const seen = new Map<number, string>();
    for (const loc of this.locations()) {
      if (loc.primarySalesRepId != null && loc.salesrepName) {
        if (!seen.has(loc.primarySalesRepId)) seen.set(loc.primarySalesRepId, loc.salesrepName);
      }
      const a = loc.assignment;
      if (a?.sellerId != null && a.sellerName && !seen.has(a.sellerId)) {
        seen.set(a.sellerId, a.sellerName);
      }
    }
    return [...seen.entries()]
      .map(([id, name]) => ({ id, name }))
      .sort((x, y) => x.name.localeCompare(y.name));
  });

  bulkCount(): number {
    return this.bulkSelected().size;
  }

  constructor() {
    const id = this.dcId();
    if (id) this.store.dispatch(LiveActions.loadLocations({ dcId: id }));
    this.loadSellerColors();

    effect(() => {
      const data = this.mappable();
      const sel = this.bulkSelected();
      const overrides = this.customColors();
      const cluster = this.clusterEnabled();
      const m = this.map;
      if (!m || !m.isStyleLoaded()) return;
      const fc = toFeatureCollection(data, sel, overrides);
      const src = m.getSource('locations') as maplibregl.GeoJSONSource | undefined;
      // Cluster config can't be mutated post-create — full rebuild on toggle.
      if (!src || cluster !== this.lastCluster) {
        this.rebuildSource(fc, cluster);
        this.lastCluster = cluster;
      } else {
        src.setData(fc);
      }
      if (data.length && sel.size === 0) this.fitTo(data);
    });
  }

  private lastCluster = true;

  toggleCluster(): void {
    this.clusterEnabled.update((v) => !v);
  }

  private loadSellerColors(): void {
    this.api.sellerColors().subscribe({
      next: (colors) => this.customColors.set(colors),
      error: () => undefined
    });
  }

  setSellerColor(key: string, event: Event): void {
    const color = (event.target as HTMLInputElement).value;
    const sellerId = Number(key);
    if (!Number.isFinite(sellerId) || sellerId <= 0) return;
    this.api.setSellerColor(sellerId, color).subscribe({
      next: () => this.customColors.update((c) => ({ ...c, [key]: color })),
      error: () => undefined
    });
  }

  resetSellerColor(key: string, event: Event): void {
    event.stopPropagation();
    const sellerId = Number(key);
    if (!Number.isFinite(sellerId) || sellerId <= 0) return;
    this.api.deleteSellerColor(sellerId).subscribe({
      next: () =>
        this.customColors.update((c) => {
          const next = { ...c };
          delete next[key];
          return next;
        }),
      error: () => undefined
    });
  }

  ngAfterViewInit(): void {
    this.map = new maplibregl.Map({
      container: this.mapContainer.nativeElement,
      style: environment.mapStyleUrl,
      center: [-95.7129, 37.0902],
      zoom: 4,
      boxZoom: false
    });
    this.map.addControl(new maplibregl.NavigationControl(), 'top-right');
    this.map.on('load', () => {
      this.rebuildSource(
        toFeatureCollection(this.mappable(), this.bulkSelected(), this.customColors()),
        this.clusterEnabled()
      );
      this.bindInteractions();
      if (this.mappable().length) this.fitTo(this.mappable());
    });
    this.destroyRef.onDestroy(() => this.map?.remove());
  }

  toggleRectangleMode(): void {
    const enabled = !this.rectangleMode();
    this.rectangleMode.set(enabled);
    if (enabled) this.map?.dragPan.disable();
    else {
      this.map?.dragPan.enable();
      this.hideSelectionBox();
    }
  }

  closePanel(): void {
    this.selected.set(null);
  }

  clearBulk(): void {
    this.bulkSelected.set(new Set());
  }

  onBulkSellerChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.bulkSellerId.set(value ? Number(value) : null);
  }

  applyBulk(): void {
    const sellerId = this.bulkSellerId();
    const ids = [...this.bulkSelected()];
    if (sellerId == null || ids.length === 0) return;
    const seller = this.sellerOptions().find((s) => s.id === sellerId);
    const byId = new Map(this.locations().map((l) => [l.siteUseID, l]));
    const liveBySite: Record<string, Record<string, unknown>> = {};
    const expectedVersions: Record<string, number> = {};
    for (const id of ids) {
      const loc = byId.get(id);
      if (!loc) continue;
      liveBySite[id] = {
        liveSellerId: loc.primarySalesRepId,
        liveSellerName: loc.salesrepName,
        locationNumber: loc.locationNumber,
        customerId: loc.customerId
      };
      expectedVersions[id] = loc.assignment?.version ?? 0;
    }
    this.bulkSaving.set(true);
    this.api
      .bulkAssign({
        siteUseIds: ids,
        sellerId,
        sellerName: seller?.name ?? null,
        dcId: this.dcId(),
        dcName: (this.currentDc()?.dc_name as string | undefined) ?? null,
        market: (this.currentDc()?.market as string | undefined) ?? null,
        region: (this.currentDc()?.region as string | undefined) ?? null,
        liveBySite,
        expectedVersions
      })
      .subscribe({
        next: (res) => {
          if (res.conflicts.length > 0) {
            this.bulkSelected.set(new Set(res.conflicts.map((c) => c.siteUseId)));
            alert(
              `${res.ok.length} updated. ${res.conflicts.length} skipped — version changed by another user. Reload, review, retry.`
            );
          } else {
            this.bulkSelected.set(new Set());
          }
          this.bulkSellerId.set(null);
          this.bulkSaving.set(false);
          this.rectangleMode.set(false);
          this.map?.dragPan.enable();
          this.store.dispatch(LiveActions.loadLocations({ dcId: this.dcId() }));
        },
        error: () => this.bulkSaving.set(false)
      });
  }

  private rebuildSource(data: GeoJSON.FeatureCollection, cluster: boolean): void {
    const m = this.map;
    if (!m) return;
    // Tear down existing layers/source so cluster config can change.
    for (const id of ['clusters', 'cluster-count', 'loc-pins']) {
      if (m.getLayer(id)) m.removeLayer(id);
    }
    if (m.getSource('locations')) m.removeSource('locations');

    m.addSource('locations', {
      type: 'geojson',
      data,
      cluster,
      clusterRadius: 50,
      clusterMaxZoom: 12
    });

    if (cluster) {
      m.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'locations',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            'rgba(11, 107, 203, 0.18)',
            50,
            'rgba(11, 107, 203, 0.28)',
            200,
            'rgba(11, 107, 203, 0.42)'
          ],
          'circle-stroke-color': '#0b6bcb',
          'circle-stroke-width': 1,
          'circle-radius': ['step', ['get', 'point_count'], 14, 50, 18, 200, 24]
        }
      });
      m.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'locations',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': ['get', 'point_count_abbreviated'],
          'text-font': ['Noto Sans Regular'],
          'text-size': 11
        },
        paint: {
          'text-color': '#0b3d75'
        }
      });
    }

    const pinLayer: maplibregl.LayerSpecification = {
      id: 'loc-pins',
      type: 'circle',
      source: 'locations',
      paint: {
        'circle-radius': ['case', ['get', 'selected'], 9, 7],
        'circle-color': ['get', 'color'],
        'circle-stroke-color': [
          'case',
          ['get', 'selected'],
          '#0f1722',
          ['match', ['get', 'lat_source'], 'census', '#b25b00', '#ffffff']
        ],
        'circle-stroke-width': [
          'case',
          ['get', 'selected'],
          3,
          ['match', ['get', 'lat_source'], 'census', 2, 1.5]
        ],
        'circle-opacity': 0.9
      }
    };
    if (cluster) pinLayer.filter = ['!', ['has', 'point_count']];
    m.addLayer(pinLayer);
  }

  private bindInteractions(): void {
    const m = this.map;
    if (!m) return;
    m.on('click', 'loc-pins', (event) => {
      const f = event.features?.[0];
      if (!f) return;
      const siteUseID = String(f.properties?.['siteUseID'] ?? '');
      if (this.rectangleMode()) {
        // In select mode, click toggles individual pin selection.
        this.togglePinSelection(siteUseID);
      } else {
        // Default: open detail panel for that pin.
        const hit = this.locations().find((r) => r.siteUseID === siteUseID) ?? null;
        this.selected.set(hit);
      }
    });
    m.on('mouseenter', 'loc-pins', () => {
      m.getCanvas().style.cursor = 'pointer';
    });
    m.on('mouseleave', 'loc-pins', () => {
      m.getCanvas().style.cursor = '';
    });

    m.on('click', 'clusters', (event) => {
      const f = event.features?.[0];
      if (!f) return;
      const clusterId = f.properties?.['cluster_id'];
      const pointCount = Number(f.properties?.['point_count'] ?? 0);
      const src = m.getSource('locations') as maplibregl.GeoJSONSource;
      if (!src || clusterId == null) return;
      if (this.rectangleMode()) {
        // Select-all-in-cluster: pull every leaf and add to bulk selection.
        this.selectClusterLeaves(src, clusterId, pointCount);
        return;
      }
      src.getClusterExpansionZoom(clusterId).then((zoom) => {
        const geom = f.geometry as GeoJSON.Point;
        m.easeTo({ center: geom.coordinates as [number, number], zoom });
      });
    });
    m.on('mouseenter', 'clusters', () => {
      m.getCanvas().style.cursor = 'pointer';
    });
    m.on('mouseleave', 'clusters', () => {
      m.getCanvas().style.cursor = '';
    });

    m.on('mousedown', (event) => this.beginRectangle(event));
    m.on('mousemove', (event) => this.updateRectangle(event));
    m.on('mouseup', (event) => this.finishRectangle(event));
  }

  private togglePinSelection(siteUseID: string): void {
    this.bulkSelected.update((s) => {
      const next = new Set(s);
      if (next.has(siteUseID)) next.delete(siteUseID);
      else next.add(siteUseID);
      return next;
    });
  }

  private beginRectangle(event: MapMouseEvent): void {
    if (!this.rectangleMode() || !this.map) return;
    event.preventDefault();
    this.dragStart = event.point;
    this.showSelectionBox(event.point, event.point);
  }

  private updateRectangle(event: MapMouseEvent): void {
    if (!this.rectangleMode() || !this.dragStart) return;
    this.showSelectionBox(this.dragStart, event.point);
  }

  private finishRectangle(event: MapMouseEvent): void {
    if (!this.rectangleMode() || !this.dragStart || !this.map) return;
    const start = this.dragStart;
    this.dragStart = undefined;
    this.hideSelectionBox();
    const m = this.map;
    const layers = ['loc-pins'];
    if (m.getLayer('clusters')) layers.push('clusters');
    const features = m.queryRenderedFeatures([start, event.point], { layers });
    const ids = new Set(this.bulkSelected());
    const src = m.getSource('locations') as maplibregl.GeoJSONSource | undefined;
    const clusterPromises: Promise<void>[] = [];
    for (const f of features) {
      const clusterId = f.properties?.['cluster_id'];
      if (clusterId != null && src) {
        const count = Number(f.properties?.['point_count'] ?? 0);
        clusterPromises.push(
          src.getClusterLeaves(clusterId, count, 0).then((leaves) => {
            for (const l of leaves) {
              const id = String(l.properties?.['siteUseID'] ?? '');
              if (id) ids.add(id);
            }
          })
        );
      } else {
        const id = String(f.properties?.['siteUseID'] ?? '');
        if (id) ids.add(id);
      }
    }
    if (clusterPromises.length) {
      Promise.all(clusterPromises).then(() => this.bulkSelected.set(ids));
    } else {
      this.bulkSelected.set(ids);
    }
  }

  private selectClusterLeaves(
    src: maplibregl.GeoJSONSource,
    clusterId: number,
    count: number
  ): void {
    src.getClusterLeaves(clusterId, count, 0).then((leaves) => {
      const ids = new Set(this.bulkSelected());
      for (const l of leaves) {
        const id = String(l.properties?.['siteUseID'] ?? '');
        if (id) ids.add(id);
      }
      this.bulkSelected.set(ids);
    });
  }

  private showSelectionBox(start: Point, end: Point): void {
    const box = this.selectionBox.nativeElement;
    const left = Math.min(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const width = Math.abs(start.x - end.x);
    const height = Math.abs(start.y - end.y);
    box.style.display = 'block';
    box.style.left = `${left}px`;
    box.style.top = `${top}px`;
    box.style.width = `${width}px`;
    box.style.height = `${height}px`;
  }

  private hideSelectionBox(): void {
    this.selectionBox.nativeElement.style.display = 'none';
  }

  private fitTo(rows: LiveLocation[]): void {
    if (!this.map || !rows.length) return;
    const bounds = new maplibregl.LngLatBounds();
    for (const r of rows) {
      bounds.extend([r.longitude as number, r.latitude as number]);
    }
    this.map.fitBounds(bounds, { padding: 60, maxZoom: 11, animate: false });
  }
}

function hasCoords(r: LiveLocation): boolean {
  return r.latitude != null && r.longitude != null;
}

function toFeatureCollection(
  rows: LiveLocation[],
  selected: Set<string>,
  overrides: Record<string, string> = {}
): GeoJSON.FeatureCollection {
  const features: PinFeature[] = rows.map((r) => {
    const key = effectiveSellerKey(r);
    return {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [r.longitude as number, r.latitude as number] },
      properties: {
        siteUseID: r.siteUseID,
        locationNumber: r.locationNumber,
        dba_name: r.dba_name ?? null,
        salesrepName: r.salesrepName,
        lat_source: r.lat_source ?? 'source',
        selected: selected.has(r.siteUseID),
        sellerKey: key,
        color: sellerColor(key, overrides)
      }
    };
  });
  return { type: 'FeatureCollection', features } as GeoJSON.FeatureCollection;
}
