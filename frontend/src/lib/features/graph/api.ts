import { api, createSSEConnection } from '$lib/core/api/client';
import type {
  ConceptSource,
  DocumentThemes,
  GenerationJob,
  GraphCheckpoint,
  GraphCheckpointDetail,
  GraphResponse,
  TrackedConcept,
} from './types';

export async function getGraph(
  projectId?: string,
  documentIds?: string[],
  depth: number = 2,
  force: boolean = false,
): Promise<GraphResponse> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (documentIds?.length) params.set('document_ids', documentIds.join(','));
  params.set('depth', String(depth));
  if (force) params.set('force', 'true');
  return api.get<GraphResponse | null>(`/graph?${params}`).then((r) => ({
    nodes: r?.nodes ?? [],
    edges: r?.edges ?? [],
  }));
}

export async function startGraphGeneration(projectId: string): Promise<GenerationJob> {
  return api.post<GenerationJob>('/graph/generate', {
    project_id: projectId,
    force: true,
  });
}

export async function listGraphHistory(projectId: string): Promise<GraphCheckpoint[]> {
  const params = new URLSearchParams({ project_id: projectId });
  return api
    .get<{ checkpoints?: GraphCheckpoint[] | null }>(`/graph/history?${params}`)
    .then((r) => r?.checkpoints ?? []);
}

export async function getGraphCheckpoint(checkpointId: string): Promise<GraphCheckpointDetail | null> {
  return api.get<GraphCheckpointDetail | null>(`/graph/history/${checkpointId}`).then((r) => {
    if (!r) return null;
    return {
      ...r,
      graph: {
        nodes: r.graph?.nodes ?? [],
        edges: r.graph?.edges ?? [],
      },
    };
  });
}

export async function setCheckpointFavourite(
  checkpointId: string,
  isFavourite: boolean,
): Promise<GraphCheckpoint> {
  return api.patch<GraphCheckpoint>(`/graph/history/${checkpointId}`, { is_favourite: isFavourite });
}

export async function deleteGraphCheckpoint(checkpointId: string): Promise<void> {
  await api.delete(`/graph/history/${checkpointId}`);
}

export async function getDocumentThemes(projectId: string): Promise<DocumentThemes[]> {
  const params = new URLSearchParams({ project_id: projectId });
  return api
    .get<{ documents?: DocumentThemes[] | null }>(`/graph/themes?${params}`)
    .then((r) => r?.documents ?? []);
}

export async function refineSearchQuery(projectId: string, query: string): Promise<string[]> {
  return api
    .post<{ matches?: string[] | null }>('/graph/search', { project_id: projectId, query })
    .then((r) => r?.matches ?? []);
}

export function streamConceptSummary(
  projectId: string,
  concept: string,
  onChunk: (text: string) => void,
  onSources: (sources: ConceptSource[]) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): () => void {
  return createSSEConnection(
    '/graph/concepts/summary',
    { project_id: projectId, label: concept },
    onChunk,
    onDone,
    onError,
    (sources) => onSources((sources as ConceptSource[] | null) ?? []),
  );
}

export async function listTrackedConcepts(projectId: string): Promise<TrackedConcept[]> {
  const params = new URLSearchParams({ project_id: projectId });
  return api
    .get<{ concepts?: TrackedConcept[] | null }>(`/graph/concepts/tracked?${params}`)
    .then((r) => r?.concepts ?? []);
}

export async function addTrackedConcept(projectId: string, concept: string): Promise<TrackedConcept> {
  return api.post<TrackedConcept>('/graph/concepts/tracked', { project_id: projectId, concept });
}

export async function removeTrackedConcept(conceptId: string): Promise<void> {
  await api.delete(`/graph/concepts/tracked/${conceptId}`);
}
