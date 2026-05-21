import { ApplicationConfig, isDevMode } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { provideEffects } from '@ngrx/effects';
import { provideStore } from '@ngrx/store';
import { provideStoreDevtools } from '@ngrx/store-devtools';

import { authInterceptor } from './core/interceptors/auth.interceptor';
import { routes } from './app.routes';
import { MarketsEffects, marketsFeature } from './store/markets';
import { DatasetsEffects, datasetsFeature } from './store/datasets';
import { TerritoryEffects, territoryFeature } from './store/territory';
import { LiveEffects, liveFeature } from './store/live';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideStore({
      [marketsFeature.name]: marketsFeature.reducer,
      [datasetsFeature.name]: datasetsFeature.reducer,
      [territoryFeature.name]: territoryFeature.reducer,
      [liveFeature.name]: liveFeature.reducer
    }),
    provideEffects(MarketsEffects, DatasetsEffects, TerritoryEffects, LiveEffects),
    provideStoreDevtools({ maxAge: 25, logOnly: !isDevMode() })
  ]
};
