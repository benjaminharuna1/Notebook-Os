import { get } from 'svelte/store';
import { api, BASE_URL } from '$lib/core/api/client';
import { token } from '$lib/features/auth/store';
import type { IngestionResponse, IngestionStatus } from './types';

export async function uploadFile(file: File, projectId?: string): Promise<IngestionResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (projectId) formData.append('project_id', projectId);

  const authToken = get(token);
  const response = await fetch(`${BASE_URL}/ingest/file`, {
    method: 'POST',
    headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return response.json();
}

export async function getIngestionStatus(documentId: string): Promise<IngestionStatus> {
  return api.get<IngestionStatus>(`/ingest/status/${documentId}`);
}

export async function pauseIngestion(documentId: string): Promise<{ status: string }> {
  return api.post<{ status: string }>(`/ingest/${documentId}/pause`, {});
}

export async function resumeIngestion(documentId: string): Promise<{ status: string }> {
  return api.post<{ status: string }>(`/ingest/${documentId}/resume`, {});
}

export async function reprocessIngestion(documentId: string): Promise<{ status: string }> {
  return api.post<{ status: string }>(`/ingest/${documentId}/reprocess`, {});
}
