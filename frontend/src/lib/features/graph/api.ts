import { api } from '$lib/core/api/client';
import type { GraphResponse } from './types';

export async function getGraph(projectId?: string, documentIds?: string[], depth: number = 2): Promise<GraphResponse> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (documentIds?.length) params.set('document_ids', documentIds.join(','));
  params.set('depth', String(depth));
  return api.get<GraphResponse>(`/graph?${params}`);
}
