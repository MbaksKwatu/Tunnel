export type AnalysisState = 'idle' | 'uploading' | 'polling' | 'exporting' | 'done' | 'error';

export interface QueuedStatement {
  id: string;
  fileName: string;
  status: 'uploading' | 'processing' | 'ready' | 'failed';
}

export interface EntityBreakdownRow {
  entityId: string;
  entityName: string;
  role: string;
  totalAbsCents: number;
  pctBps: number; // basis points, display as pctBps/100 + '%'
  txnCount: number;
}

export type StageStatus = 'done' | 'active' | 'queued' | 'failed';

export interface PipelineStage {
  name: string;
  detail: string;
  progress: string;
  pct?: number;
  status: StageStatus;
}

export interface DrillModalState {
  title: string;
  color: string;
  rows: Array<Record<string, unknown>>;
  type: 'entity' | 'txn';
}

export interface ParserRequestDoc {
  docId: string;
  fileName: string;
  errorMessage: string;
}

export interface ParserRequestForm {
  bankName: string;
  country: string;
  accountType: string;
  notes: string;
}
