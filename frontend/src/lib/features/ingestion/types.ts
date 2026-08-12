export interface IngestionResponse {
  document_id: string;
  status: string;
  estimated_time: number;
}

export interface IngestionStatus {
  document_id: string;
  status: 'pending' | 'processing' | 'indexed' | 'failed';
  progress: number;
  chunks_created: number;
  error?: string;
}
