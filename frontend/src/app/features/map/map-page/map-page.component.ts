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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Store } from '@ngrx/store';
import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';

import { environment } from '../../../../environments/environment';
import { DatasetApiService } from '../../../core/api/dataset-api.service';
import { MapFilters, toFilterParams } from '../../../core/models/map-filters.model';
import {
  TerritoryActions,
  selectAccounts,
  selectAssignmentSellerId,
  selectFilters,
  selectFirstSelected,
  selectLoadingAccounts,
  selectSaving,
  selectSelectedFeatures,
  selectSelectionIds,
  selectSellers,
  selectStatusMessage,
  selectTotalCount
} from '../../../store/territory';
import { MapBulkBarComponent } from './map-bulk-bar/map-bulk-bar.component';
import { MapFiltersComponent } from './map-filters/map-filters.component';
import { MapPinDetailComponent } from './map-pin-detail/map-pin-detail.component';
import { MapSellerSummaryComponent } from './map-seller-summary/map-seller-summary.component';

@Component({
  selector: 'atd-map-page',
  standalone: true,
  imports: [
    RouterLink,
    MapFiltersComponent,
    MapPinDetailComponent,
    MapBulkBarComponent,
    MapSellerSummaryComponent
  ],
  templateUrl: './map-page.component.html',
  styleUrl: './map-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MapPageComponent implements AfterViewInit {
  @ViewChild('mapContainer', { static: true }) private readonly mapContainer!: ElementRef<HTMLElement>;
  @ViewChild('selectionBox', { static: true }) private readonly selectionBox!: ElementRef<HTMLElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly store = inject(Store);
  private readonly datasetApi = inject(DatasetApiService);
  private readonly destroyRef = inject(DestroyRef);
  private map?: MapLibreMap;
  private dragStart?: { x: number; y: number };
  private readonly datasetId = this.route.snapshot.paramMap.get('datasetId') ?? '';

  readonly accounts = this.store.selectSignal(selectAccounts);
  readonly sellers = this.store.selectSignal(selectSellers);
  readonly filters = this.store.selectSignal(selectFilters);
  readonly selectionIds = this.store.selectSignal(selectSelectionIds);
  readonly selectedFeatures = this.store.selectSignal(selectSelectedFeatures);
  readonly firstSelected = this.store.selectSignal(selectFirstSelected);
  readonly assignmentSellerId = this.store.selectSignal(selectAssignmentSellerId);
  readonly saving = this.store.selectSignal(selectSaving);
  readonly statusMessage = this.store.selectSignal(selectStatusMessage);
  readonly totalCount = this.store.selectSignal(selectTotalCount);
  readonly loading = this.store.selectSignal(selectLoadingAccounts);

  readonly rectangleSelectMode = signal(false);
  readonly visiblePinCount = signal(0);

  readonly dcs = computed(() => this.distinct('dc'));
  readonly primaryPrograms = computed(() => this.distinct('primaryProgram'));
  readonly secondaryPrograms = computed(() => this.distinct('secondaryProgram'));

  readonly selectedCount = computed(() => this.selectionIds().length);

  constructor() {
    if (this.datasetId) {
      this.store.dispatch(TerritoryActions.openDataset({ datasetId: this.datasetId }));
    }

    effect(() => {
      const data = this.accounts();
      if (!this.map || !data) return;
      const styled = this.withPinIcons(data);
      this.addSellerPinImages(styled);
      const source = this.map.getSource('accounts') as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(styled);
        this.updateRenderedCounts();
        this.updateSelectedLayer();
      } else {
        this.addAccountLayers(styled);
      }
    });

    effect(() => {
      if (!this.map) return;
      this.updateSelectedLayer();
    });
  }

  ngAfterViewInit(): void {
    this.map = new maplibregl.Map({
      container: this.mapContainer.nativeElement,
      style: this.mapStyle(),
      center: [-118.2437, 34.0522],
      zoom: 8
    });

    this.map.addControl(new maplibregl.NavigationControl(), 'top-right');
    this.map.on('load', () => {
      this.bindMapInteractions();
      const data = this.accounts();
      if (data) {
        const styled = this.withPinIcons(data);
        this.addSellerPinImages(styled);
        this.addAccountLayers(styled);
      }
    });

    this.destroyRef.onDestroy(() => this.map?.remove());
  }

  onFiltersChange(partial: Partial<MapFilters>): void {
    this.store.dispatch(TerritoryActions.updateFilters({ filters: partial }));
  }

  onFiltersClear(): void {
    this.store.dispatch(TerritoryActions.clearFilters());
  }

  toggleRectangleSelect(): void {
    const enabled = !this.rectangleSelectMode();
    this.rectangleSelectMode.set(enabled);
    if (enabled) {
      this.map?.dragPan.disable();
    } else {
      this.map?.dragPan.enable();
      this.hideSelectionBox();
    }
  }

  onAssignmentSellerChange(sellerId: string): void {
    this.store.dispatch(TerritoryActions.setAssignmentSeller({ sellerId }));
  }

  saveSingle(): void {
    const account = this.firstSelected();
    const sellerId = this.assignmentSellerId();
    if (!account || !sellerId) return;
    this.store.dispatch(
      TerritoryActions.saveSingleAssignment({
        accountId: String(account.properties?.['id']),
        sellerId,
        version: Number(account.properties?.['version'] ?? 0)
      })
    );
  }

  saveBulk(): void {
    const sellerId = this.assignmentSellerId();
    const accounts = this.selectedFeatures().map((feature) => ({
      accountId: String(feature.properties?.['id']),
      version: Number(feature.properties?.['version'] ?? 0)
    }));
    if (!sellerId || accounts.length === 0) return;
    this.store.dispatch(TerritoryActions.saveBulkAssignment({ accounts, sellerId }));
  }

  clearSelection(): void {
    this.store.dispatch(TerritoryActions.clearSelection());
  }

  exportAll(): void {
    window.location.href = this.datasetApi.exportUrl(this.datasetId, {});
  }

  exportFiltered(): void {
    window.location.href = this.datasetApi.exportUrl(this.datasetId, toFilterParams(this.filters()));
  }

  private bindMapInteractions(): void {
    if (!this.map) return;

    this.map.on('click', 'account-pins', (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const id = String(feature.properties?.['id'] ?? '');
      if (!id) return;
      this.store.dispatch(TerritoryActions.setSelection({ accountIds: [id] }));
    });

    this.map.on('mouseenter', 'account-pins', () => {
      if (this.map) this.map.getCanvas().style.cursor = 'pointer';
    });
    this.map.on('mouseleave', 'account-pins', () => {
      if (this.map) this.map.getCanvas().style.cursor = '';
    });

    this.map.on('mousedown', (event) => this.beginRectangleSelect(event));
    this.map.on('mousemove', (event) => this.updateRectangleSelect(event));
    this.map.on('mouseup', (event) => this.finishRectangleSelect(event));
    this.map.on('moveend', () => this.updateRenderedCounts());
    this.map.on('sourcedata', () => this.updateRenderedCounts());
  }

  private addAccountLayers(data: GeoJSON.FeatureCollection): void {
    if (!this.map) return;
    this.addPinImage();

    this.map.addSource('accounts', { type: 'geojson', data });

    this.map.addLayer({
      id: 'account-pins',
      type: 'symbol',
      source: 'accounts',
      layout: {
        'icon-image': ['get', 'pinIcon'],
        'icon-size': 1.55,
        'icon-anchor': 'bottom',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
      }
    });

    this.map.addLayer({
      id: 'account-pin-labels',
      type: 'symbol',
      source: 'accounts',
      layout: {
        'text-field': ['to-string', ['get', 'pinNumber']],
        'text-size': 13,
        'text-offset': [0, -2.15],
        'text-allow-overlap': true,
        'text-ignore-placement': true
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': 'rgba(0, 0, 0, 0.25)',
        'text-halo-width': 1
      }
    });

    this.map.addLayer({
      id: 'account-selected-pins',
      type: 'symbol',
      source: 'accounts',
      filter: ['in', ['get', 'id'], ['literal', []]],
      layout: {
        'icon-image': 'account-pin-selected',
        'icon-size': 1.85,
        'icon-anchor': 'bottom',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
      }
    });

    this.updateRenderedCounts();
  }

  private beginRectangleSelect(event: maplibregl.MapMouseEvent): void {
    if (!this.rectangleSelectMode() || !this.map) return;
    event.preventDefault();
    this.dragStart = event.point;
    this.showSelectionBox(event.point, event.point);
  }

  private updateRectangleSelect(event: maplibregl.MapMouseEvent): void {
    if (!this.dragStart) return;
    this.showSelectionBox(this.dragStart, event.point);
  }

  private finishRectangleSelect(event: maplibregl.MapMouseEvent): void {
    if (!this.map || !this.dragStart) return;
    const start = this.dragStart;
    this.dragStart = undefined;
    this.hideSelectionBox();
    const minX = Math.min(start.x, event.point.x);
    const minY = Math.min(start.y, event.point.y);
    const maxX = Math.max(start.x, event.point.x);
    const maxY = Math.max(start.y, event.point.y);
    if (Math.abs(maxX - minX) < 4 && Math.abs(maxY - minY) < 4) return;
    const features = this.map.queryRenderedFeatures(
      [
        [minX, minY],
        [maxX, maxY]
      ],
      { layers: ['account-pins'] }
    );
    const ids = Array.from(
      new Set(features.map((f) => String(f.properties?.['id'])).filter(Boolean))
    );
    this.store.dispatch(TerritoryActions.setSelection({ accountIds: ids }));
  }

  private showSelectionBox(start: { x: number; y: number }, end: { x: number; y: number }): void {
    const box = this.selectionBox.nativeElement;
    box.style.display = 'block';
    box.style.left = `${Math.min(start.x, end.x)}px`;
    box.style.top = `${Math.min(start.y, end.y)}px`;
    box.style.width = `${Math.abs(end.x - start.x)}px`;
    box.style.height = `${Math.abs(end.y - start.y)}px`;
  }

  private hideSelectionBox(): void {
    this.dragStart = undefined;
    this.selectionBox.nativeElement.style.display = 'none';
  }

  private updateSelectedLayer(): void {
    if (!this.map || !this.map.getLayer('account-selected-pins')) return;
    this.map.setFilter('account-selected-pins', [
      'in',
      ['get', 'id'],
      ['literal', this.selectionIds()]
    ]);
  }

  private updateRenderedCounts(): void {
    if (!this.map || !this.map.getLayer('account-pins')) return;
    const pins = this.map.queryRenderedFeatures(undefined, { layers: ['account-pins'] });
    this.visiblePinCount.set(pins.length);
  }

  private addPinImage(): void {
    if (!this.map || this.map.hasImage('account-pin-selected')) return;
    this.map.addImage('account-pin-selected', this.createPinImage('#f59e0b', '#0f1722'), {
      pixelRatio: 2
    });
  }

  private addSellerPinImages(data: GeoJSON.FeatureCollection): void {
    if (!this.map) return;
    for (const feature of data.features) {
      const iconName = feature.properties?.['pinIcon'];
      const color = feature.properties?.['sellerColor'];
      if (typeof iconName !== 'string' || typeof color !== 'string' || this.map.hasImage(iconName)) {
        continue;
      }
      this.map.addImage(iconName, this.createPinImage(color, '#ffffff'), { pixelRatio: 2 });
    }
  }

  private withPinIcons(data: GeoJSON.FeatureCollection): GeoJSON.FeatureCollection {
    return {
      ...data,
      features: data.features.map((feature) => {
        const color = this.cleanHexColor(feature.properties?.['sellerColor']);
        return {
          ...feature,
          properties: {
            ...feature.properties,
            sellerColor: color,
            pinIcon: `account-pin-${color.replace('#', '')}`
          }
        };
      })
    };
  }

  private cleanHexColor(value: unknown): string {
    if (typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value)) {
      return value.toLowerCase();
    }
    return '#7b8794';
  }

  private createPinImage(fill: string, stroke: string): ImageData {
    const width = 48;
    const height = 64;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas not available');
    ctx.clearRect(0, 0, width, height);
    ctx.beginPath();
    ctx.arc(24, 22, 15, Math.PI * 0.08, Math.PI * 1.92);
    ctx.lineTo(24, 58);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = 4;
    ctx.strokeStyle = stroke;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(24, 22, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    return ctx.getImageData(0, 0, width, height);
  }

  private distinct(propertyName: string): string[] {
    const data = this.accounts();
    if (!data) return [];
    const set = new Set<string>();
    for (const feature of data.features) {
      const value = feature.properties?.[propertyName];
      if (typeof value === 'string' && value) set.add(value);
    }
    return Array.from(set).sort();
  }

  private mapStyle(): string | maplibregl.StyleSpecification {
    if (environment.mapStyleUrl) return environment.mapStyleUrl;
    return {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors'
        }
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
    };
  }

  // Suppress unused-import warning on takeUntilDestroyed (kept for future API streams)
  private readonly _keepImports = takeUntilDestroyed;
}
