export interface GraphNode {
  id: string;
  label: string;
  type: string;
  weight: number;
  x?: number;
  y?: number;
  cluster?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  weight: number;
  edge_type?: 'citation' | 'similarity' | string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ClusterInfo {
  id: string;
  label: string;
  summary: string;
  size: number;
}

export interface LiteratureMapResponse extends GraphResponse {
  clusters: ClusterInfo[];
  generated_at?: string | null;
}

export interface LiteratureEntry {
  paper_id: string;
  title: string;
  citation?: string | null;
  research_objective?: string | null;
  methodology?: string | null;
  key_findings?: string | null;
  limitations?: string | null;
  relevance?: string | null;
  apa_reference?: string | null;
  auto_generated: boolean;
}

export interface PaperMeta {
  doc_id?: string;
  year?: number | null;
  authors?: string[];
  doi?: string | null;
  abstract?: string | null;
  verification_status?: string | null;
  apa_reference?: string | null;
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
