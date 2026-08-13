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
