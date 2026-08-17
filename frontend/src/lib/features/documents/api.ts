import { api } from '$lib/core/api/client';
import type { DocumentList, Document } from './types';

export async function listDocuments(params?: {
  page?: number;
  limit?: number;
  search?: string;
  file_type?: string;
  project_id?: string;
}): Promise<DocumentList> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set('page', String(params.page));
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.search) searchParams.set('search', params.search);
  if (params?.file_type) searchParams.set('file_type', params.file_type);
  if (params?.project_id) searchParams.set('project_id', params.project_id);
  return api.get<DocumentList>(`/documents?${searchParams}`);
}

export async function getDocument(id: string): Promise<Document> {
  return api.get<Document>(`/documents/${id}`);
}

export async function deleteDocument(id: string): Promise<{ success: boolean }> {
  return api.delete<{ success: boolean }>(`/documents/${id}`);
}

export async function deleteDocuments(
  projectId: string,
  ids: string[],
): Promise<{ success: boolean; deleted: number }> {
  return api.post<{ success: boolean; deleted: number }>(
    `/projects/${projectId}/documents/batch/delete`,
    { document_ids: ids },
  );
}

export interface OrphanInfo {
  id: string;
  title: string;
  reason: 'indexed_without_entry' | 'failed_permanently';
  file_size: number;
}

export async function findOrphans(projectId: string): Promise<{ orphans: OrphanInfo[] }> {
  return api.get<{ orphans: OrphanInfo[] }>(`/projects/${projectId}/documents/orphans`);
}

export async function cleanOrphans(
  projectId: string,
): Promise<{ success: boolean; deleted: number; reasons: Record<string, number> }> {
  return api.post<{ success: boolean; deleted: number; reasons: Record<string, number> }>(
    `/projects/${projectId}/documents/clean-orphans`,
    {},
  );
}
