export interface MapFilters {
  seller?: string;
  dc?: string;
  tirePros?: boolean;
  activate?: boolean;
  primaryProgram?: string;
  secondaryProgram?: string;
  ttmMin?: number;
  ttmMax?: number;
}

export const EMPTY_FILTERS: MapFilters = {};

export function toFilterParams(filters: MapFilters): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === '' || value === null) continue;
    out[key] = String(value);
  }
  return out;
}
