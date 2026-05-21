export interface Market {
  id: string;
  name: string;
  region?: string | null;
  is_active?: boolean;
}

export interface MarketCreateInput {
  name: string;
  region?: string | null;
}
