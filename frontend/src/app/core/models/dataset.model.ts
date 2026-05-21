export type ImportStatusName =
  | 'queued'
  | 'pending'
  | 'processing'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed';

export interface Dataset {
  id: string;
  name: string;
  market_id: string;
  import_status: ImportStatusName;
  is_active: boolean;
  row_count: number;
}

export interface ImportAccepted {
  datasetId: string;
  importJobId: string;
  status: ImportStatusName;
}

export interface ImportStatus {
  datasetId: string;
  importJobId: string;
  status: ImportStatusName;
  rowCount: number;
  processedCount: number;
  geocodeSuccessCount: number;
  geocodeFailureCount: number;
  warnings: string[];
}
