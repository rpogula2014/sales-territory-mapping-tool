import { createActionGroup, emptyProps, props } from '@ngrx/store';

import { AssignmentUpdate, BulkAssignmentResult } from '../../core/models/assignment.model';
import { MapFilters } from '../../core/models/map-filters.model';
import { Seller } from '../../core/models/seller.model';

export const TerritoryActions = createActionGroup({
  source: 'Territory',
  events: {
    'Open Dataset': props<{ datasetId: string }>(),
    'Close Dataset': emptyProps(),

    'Load Sellers': props<{ datasetId: string }>(),
    'Load Sellers Success': props<{ sellers: Seller[] }>(),
    'Load Sellers Failure': props<{ error: string }>(),

    'Update Filters': props<{ filters: Partial<MapFilters> }>(),
    'Clear Filters': emptyProps(),

    'Load Accounts': emptyProps(),
    'Load Accounts Success': props<{ data: GeoJSON.FeatureCollection }>(),
    'Load Accounts Failure': props<{ error: string }>(),

    'Set Selection': props<{ accountIds: string[] }>(),
    'Clear Selection': emptyProps(),

    'Set Assignment Seller': props<{ sellerId: string }>(),

    'Save Single Assignment': props<{ accountId: string; sellerId: string; version: number }>(),
    'Save Single Success': props<{ update: AssignmentUpdate }>(),
    'Save Bulk Assignment': props<{
      accounts: Array<{ accountId: string; version: number }>;
      sellerId: string;
    }>(),
    'Save Bulk Success': props<{ result: BulkAssignmentResult }>(),
    'Save Assignment Conflict': props<{ message: string }>(),
    'Save Assignment Failure': props<{ error: string }>()
  }
});
