export interface GraphNode {
  id: string;
  label: string;
  type: string;
  weight: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface TrackedConcept {
  id: string;
  project_id: string;
  concept: string;
  created_at?: string;
}

export interface Theme {
  concept: string;
  count: number;
}

export interface DocumentThemes {
  doc_id: string;
  doc_name: string;
  themes: Theme[];
}

export interface GraphCheckpoint {
  id: string;
  project_id: string;
  fingerprint: string;
  prefs_key: string;
  is_favourite: boolean;
  created_at: string;
  nodes: number;
  edges: number;
}

export interface GraphCheckpointDetail extends GraphCheckpoint {
  graph: GraphResponse;
}

export interface GenerationJob {
  id: string;
  status: 'running' | 'done' | 'error';
  progress: number;
  stage?: string;
  checkpoint?: GraphCheckpoint;
  error?: string;
}

export interface ConceptSource {
  title?: string | null;
  page?: number | null;
  doc_id?: string | null;
  snippet?: string | null;
}
