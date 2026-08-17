from typing import List, Optional

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    weight: float = 1.0
    x: float = 0.0
    y: float = 0.0


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    weight: float = 1.0


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphGenerateRequest(BaseModel):
    project_id: str
    document_ids: List[str] = []
    depth: int = 2
    force: bool = True


class GenerationJob(BaseModel):
    id: str
    status: str
    progress: int
    stage: Optional[str] = None
    checkpoint: Optional["GraphCheckpoint"] = None
    error: Optional[str] = None


class GraphCheckpoint(BaseModel):
    id: str
    project_id: str
    fingerprint: str
    prefs_key: str
    is_favourite: bool = False
    is_active: bool = False
    created_at: str
    nodes: int
    edges: int


class GraphCheckpointList(BaseModel):
    checkpoints: List[GraphCheckpoint]


class GraphCheckpointDetail(GraphCheckpoint):
    graph: GraphResponse


class GraphCheckpointUpdate(BaseModel):
    is_favourite: bool


class GraphSearchRequest(BaseModel):
    project_id: str
    query: str


class GraphSearchResponse(BaseModel):
    matches: List[str] = []


class GraphSummaryRequest(BaseModel):
    project_id: str
    label: str


class TrackedConcept(BaseModel):
    id: str
    project_id: str
    concept: str
    created_at: Optional[str] = None


class TrackedConceptCreate(BaseModel):
    project_id: str
    concept: str


class TrackedConceptList(BaseModel):
    concepts: List[TrackedConcept]


class Theme(BaseModel):
    concept: str
    count: int


class DocumentThemes(BaseModel):
    doc_id: str
    doc_name: str
    themes: List[Theme]


class DocumentThemesList(BaseModel):
    documents: List[DocumentThemes]


GenerationJob.model_rebuild()
