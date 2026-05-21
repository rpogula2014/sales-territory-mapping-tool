import {
  ActiveFilters,
  FilterDescriptor,
  FilterValue,
  LiveLocation
} from '../../core/models/live.model';

export function applyFilters(
  rows: LiveLocation[],
  filters: ActiveFilters,
  schema: FilterDescriptor[]
): LiveLocation[] {
  const active = Object.entries(filters).filter(([, v]) => !isEmpty(v));
  if (active.length === 0) return rows;

  const descByField = new Map(schema.map((d) => [d.field, d]));

  return rows.filter((row) =>
    active.every(([field, value]) => match(row, field, value, descByField.get(field)))
  );
}

function isEmpty(value: FilterValue): boolean {
  if (value == null) return true;
  if (Array.isArray(value) && value.length === 0) return true;
  if (typeof value === 'string' && value.trim() === '') return true;
  return false;
}

function match(
  row: LiveLocation,
  field: string,
  value: FilterValue,
  desc: FilterDescriptor | undefined
): boolean {
  const cell = (row as unknown as Record<string, unknown>)[field];

  switch (desc?.control) {
    case 'toggle': {
      const expected = value as boolean;
      return cellIsTrue(cell) === expected;
    }
    case 'range': {
      const [min, max] = value as [number, number];
      const n = typeof cell === 'number' ? cell : cell != null ? Number(cell) : NaN;
      if (Number.isNaN(n)) return false;
      return n >= min && n <= max;
    }
    case 'multiselect': {
      const picks = value as string[];
      return picks.includes(String(cell ?? ''));
    }
    case 'multiselect-tokens': {
      const picks = new Set(value as string[]);
      if (typeof cell !== 'string') return false;
      const sep = desc.separator ?? '*';
      const tokens = cell.split(sep).filter(Boolean);
      return tokens.some((t) => picks.has(t));
    }
    case 'text': {
      const q = String(value).toLowerCase();
      return String(cell ?? '').toLowerCase().includes(q);
    }
    default:
      return true;
  }
}

function cellIsTrue(cell: unknown): boolean {
  if (typeof cell === 'boolean') return cell;
  if (typeof cell === 'string') {
    const s = cell.trim().toUpperCase();
    return s === 'Y' || s === 'TRUE';
  }
  return false;
}
