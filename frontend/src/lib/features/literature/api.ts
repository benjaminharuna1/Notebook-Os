import { BASE_URL, api, createSSEConnection } from '$lib/core/api/client';
import { get } from 'svelte/store';
import { token } from '$lib/features/auth/store';
import type { SearchResponse } from '$lib/features/search/types';
import type {
  ConceptSource,
  GraphEdge,
  GraphNode,
  LiteratureEntry,
  LiteratureMapResponse,
} from '$lib/features/graph/types';

export interface LiteratureBuildJob {
  id: string;
  status: 'running' | 'done' | 'error';
  progress: number;
  stage?: string;
  error?: string;
}

export async function startLiteratureBuild(projectId: string): Promise<LiteratureBuildJob> {
  return api.post<LiteratureBuildJob>(`/projects/${projectId}/literature/build`, {});
}

export async function getLiteratureJob(
  projectId: string,
  jobId: string,
): Promise<LiteratureBuildJob> {
  return api.get<LiteratureBuildJob>(`/projects/${projectId}/literature/jobs/${jobId}`);
}

export async function getLiteratureMap(projectId: string): Promise<LiteratureMapResponse> {
  return api
    .get<LiteratureMapResponse | null>(`/projects/${projectId}/literature/map`)
    .then((r) => r ?? { nodes: [], edges: [], clusters: [] });
}

export async function getLiteratureEntries(projectId: string): Promise<LiteratureEntry[]> {
  return api.get<LiteratureEntry[]>(`/projects/${projectId}/literature/entries`);
}

export async function updateLiteratureEntry(
  projectId: string,
  paperId: string,
  fields: Partial<LiteratureEntry>,
): Promise<LiteratureEntry> {
  return api.patch<LiteratureEntry>(`/projects/${projectId}/literature/entries/${paperId}`, fields);
}

export async function regenerateLiteratureEntry(
  projectId: string,
  paperId: string,
): Promise<LiteratureEntry> {
  return api.post<LiteratureEntry>(
    `/projects/${projectId}/literature/entries/${paperId}/regenerate`,
    {},
  );
}

export async function searchPapers(projectId: string, query: string): Promise<SearchResponse> {
  return api.post<SearchResponse>('/search', {
    query,
    top_k: 10,
    project_id: projectId,
    include_keyword: true,
  });
}

export interface MetadataCandidate {
  source?: string | null;
  doi?: string | null;
  title?: string | null;
  authors?: string[];
  year?: number | null;
  abstract?: string | null;
  container_title?: string | null;
  confidence?: number | null;
}

export interface LiteratureMetadata {
  title: string;
  authors: string[];
  year?: number | null;
  doi?: string | null;
  abstract?: string | null;
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  publisher?: string | null;
  url?: string | null;
  apa_reference?: string | null;
  verification_status?: string | null;
  metadata_user_edited?: boolean;
  extracted_doi?: string | null;
  candidates?: MetadataCandidate[];
}

export type LiteratureMetadataFields = Pick<
  LiteratureMetadata,
  'title' | 'authors' | 'year' | 'doi' | 'abstract' | 'journal' | 'volume' | 'issue' | 'pages' | 'publisher' | 'url'
>;

export async function getPaperMetadata(
  projectId: string,
  paperId: string,
): Promise<LiteratureMetadata> {
  return api.get<LiteratureMetadata>(`/projects/${projectId}/literature/entries/${paperId}/metadata`);
}

export async function updatePaperMetadata(
  projectId: string,
  paperId: string,
  fields: Partial<LiteratureMetadataFields>,
): Promise<LiteratureMetadata> {
  return api.patch<LiteratureMetadata>(
    `/projects/${projectId}/literature/entries/${paperId}/metadata`,
    fields,
  );
}

export async function applyPaperCandidate(
  projectId: string,
  paperId: string,
  index: number,
): Promise<LiteratureMetadata> {
  return api.post<LiteratureMetadata>(
    `/projects/${projectId}/literature/entries/${paperId}/candidates/apply`,
    { index },
  );
}

export async function getDocumentFileUrl(projectId: string, documentId: string): Promise<string> {
  const authToken = get(token);
  const response = await fetch(`${BASE_URL}/projects/${projectId}/documents/${documentId}/file`, {
    headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    credentials: 'include',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || `Could not load document: ${response.status}`);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function exportLiteratureMap(projectId: string): Promise<void> {
  const authToken = get(token);
  const response = await fetch(`${BASE_URL}/projects/${projectId}/literature/export`, {
    headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
    credentials: 'include',
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || `Export failed: ${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? 'literature-mapping.xlsx';
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export interface LiteratureRegenerateResult {
  paper_id: string;
  status: string | null;
}

export async function regenerateLiteratureMetadata(
  projectId: string,
  paperIds?: string[],
): Promise<{ processed: number; results: LiteratureRegenerateResult[] }> {
  return api.post<{ processed: number; results: LiteratureRegenerateResult[] }>(
    `/projects/${projectId}/literature/regenerate`,
    { paper_ids: paperIds ?? null },
  );
}

export async function exportReferencesDocx(projectId: string): Promise<void> {
  const authToken = get(token);
  const response = await fetch(
    `${BASE_URL}/projects/${projectId}/literature/references/export.docx`,
    {
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {},
      credentials: 'include',
    },
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || `Export failed: ${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? 'references.docx';
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function streamClusterSummary(
  projectId: string,
  clusterId: string,
  onChunk: (text: string) => void,
  onSources: (sources: ConceptSource[]) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): () => void {
  return createSSEConnection(
    `/projects/${projectId}/literature/clusters/summary`,
    { project_id: projectId, cluster_id: clusterId },
    onChunk,
    onDone,
    onError,
    (sources) => onSources((sources as ConceptSource[] | null) ?? []),
  );
}

export type { GraphEdge, GraphNode, LiteratureEntry };
