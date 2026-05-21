import { createActionGroup, emptyProps, props } from '@ngrx/store';

import { Market, MarketCreateInput } from '../../core/models/market.model';

export const MarketsActions = createActionGroup({
  source: 'Markets',
  events: {
    Load: emptyProps(),
    'Load Success': props<{ markets: Market[] }>(),
    'Load Failure': props<{ error: string }>(),

    Create: props<{ input: MarketCreateInput }>(),
    'Create Success': props<{ market: Market }>(),
    'Create Failure': props<{ error: string }>(),

    Remove: props<{ id: string }>(),
    'Remove Success': props<{ id: string }>(),
    'Remove Failure': props<{ error: string }>()
  }
});
