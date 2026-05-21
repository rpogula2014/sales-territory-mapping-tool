import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'home' },
  {
    path: 'home',
    loadComponent: () =>
      import('./features/home/home-page/home-page.component').then((m) => m.HomePageComponent)
  },
  {
    path: 'markets',
    loadComponent: () =>
      import('./features/markets/market-picker-page/market-picker-page.component').then(
        (m) => m.MarketPickerPageComponent
      )
  },
  {
    path: 'map/:datasetId',
    loadComponent: () =>
      import('./features/map/map-page/map-page.component').then((m) => m.MapPageComponent)
  },
  {
    path: 'live',
    pathMatch: 'full',
    redirectTo: 'live/dcs'
  },
  {
    path: 'live/dcs',
    loadComponent: () =>
      import('./features/live/live-dc-picker-page/live-dc-picker-page.component').then(
        (m) => m.LiveDcPickerPageComponent
      )
  },
  {
    path: 'live/dcs/:dcId/locations',
    loadComponent: () =>
      import('./features/live/live-locations-page/live-locations-page.component').then(
        (m) => m.LiveLocationsPageComponent
      )
  },
  {
    path: 'live/changes',
    loadComponent: () =>
      import('./features/live/live-changes-page/live-changes-page.component').then(
        (m) => m.LiveChangesPageComponent
      )
  },
  {
    path: 'live/dcs/:dcId/map',
    loadComponent: () =>
      import('./features/live/live-map-page/live-map-page.component').then(
        (m) => m.LiveMapPageComponent
      )
  },
  {
    path: 'admin/import',
    loadComponent: () =>
      import('./features/admin/admin-import-page/admin-import-page.component').then(
        (m) => m.AdminImportPageComponent
      )
  },
  {
    path: 'admin/markets',
    loadComponent: () =>
      import('./features/admin/admin-markets-page/admin-markets-page.component').then(
        (m) => m.AdminMarketsPageComponent
      )
  }
];
