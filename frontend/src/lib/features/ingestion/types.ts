export type IngestionStatusValue = 'queued' | 'processing' | 'paused' | 'indexed' | 'failed';

export interface IngestionResponse {
  document_id: string;
  status: string;
  estimated_time: number;
}

export interface IngestionStatus {
  document_id: string;
  status: IngestionStatusValue;
  progress: number;
  chunks_created: number;
  error?: string;
}
