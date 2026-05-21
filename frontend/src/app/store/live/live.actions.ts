import { createActionGroup, emptyProps, props } from '@ngrx/store';

import {
  AssignmentBlock,
  AssignmentPatchInput,
  FilterDescriptor,
  FilterValue,
  LiveDc,
  LiveLocation
} from '../../core/models/live.model';

export const LiveActions = createActionGroup({
  source: 'Live',
  events: {
    'Load Regions': emptyProps(),
    'Load Regions Success': props<{ regions: string[] }>(),
    'Load Regions Failure': props<{ error: string }>(),

    'Region Selected': props<{ region: string | null }>(),

    'Load Markets': props<{ region: string | null }>(),
    'Load Markets Success': props<{ markets: string[] }>(),
    'Load Markets Failure': props<{ error: string }>(),

    'Market Selected': props<{ market: string | null }>(),

    'Load Dcs': props<{ region: string | null; market: string | null }>(),
    'Load Dcs Success': props<{ dcs: LiveDc[] }>(),
    'Load Dcs Failure': props<{ error: string }>(),

    'Dc Selected': props<{ dcId: number | null }>(),

    'Load Locations': props<{ dcId: number }>(),
    'Load Locations Success': props<{ locations: LiveLocation[] }>(),
    'Load Locations Failure': props<{ error: string }>(),

    'Load Filter Schema': props<{ dcId: number }>(),
    'Load Filter Schema Success': props<{ schema: FilterDescriptor[] }>(),
    'Load Filter Schema Failure': props<{ error: string }>(),

    'Set Filter': props<{ field: string; value: FilterValue }>(),
    'Clear Filters': emptyProps(),

    'Save Assignment': props<{ siteUseId: string; input: AssignmentPatchInput }>(),
    'Save Assignment Success': props<{ siteUseId: string; assignment: AssignmentBlock }>(),
    'Save Assignment Failure': props<{ error: string }>(),

    'Revert Assignment': props<{ siteUseId: string; expectedVersion: number }>(),
    'Revert Assignment Success': props<{ siteUseId: string }>(),
    'Revert Assignment Failure': props<{ error: string }>(),

    'Reconfirm Assignment': props<{
      siteUseId: string;
      liveSellerId: number | null;
      liveSellerName: string | null;
      expectedVersion: number;
    }>(),
    'Reconfirm Assignment Success': props<{ siteUseId: string; assignment: AssignmentBlock }>(),
    'Reconfirm Assignment Failure': props<{ error: string }>(),

    'Set Status Filter': props<{ statuses: string[] }>()
  }
});
