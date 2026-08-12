import { api } from '$lib/core/api/client';
import type { IngestionResponse, IngestionStatus } from './types';

export async function uploadFile(file: File): Promise<IngestionResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/v1/ingest/file', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) throw new Error('Upload failed');
  return response.json();
}

export async function getIngestionStatus(documentId: string): Promise<IngestionStatus> {
  return api.get<IngestionStatus>(`/ingest/status/${documentId}`);
}
