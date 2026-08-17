from typing import List, Optional

from pydantic import BaseModel


class PaperNode(BaseModel):
    id: str
    label: str
    type: str = "paper"
    weight: float = 1.0
    x: float = 0.0
    y: float = 0.0
    cluster: Optional[str] = None
    meta: Optional[dict] = None


class PaperEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0
    edge_type: str = "similarity"


class ClusterInfo(BaseModel):
    id: str
    label: str
    summary: str = ""
    size: int = 0


class LiteratureMapResponse(BaseModel):
    nodes: List[PaperNode]
    edges: List[PaperEdge]
    clusters: List[ClusterInfo] = []
    generated_at: Optional[str] = None


class LiteratureBuildJob(BaseModel):
    id: str
    status: str
    progress: int
    stage: Optional[str] = None
    error: Optional[str] = None


class LiteratureClusterSummaryRequest(BaseModel):
    project_id: str
    cluster_id: str


class LiteratureEntry(BaseModel):
    paper_id: str
    title: str = ""
    citation: Optional[str] = None
    research_objective: Optional[str] = None
    methodology: Optional[str] = None
    key_findings: Optional[str] = None
    limitations: Optional[str] = None
    relevance: Optional[str] = None
    apa_reference: Optional[str] = None
    auto_generated: bool = False


class LiteratureEntryUpdate(BaseModel):
    citation: Optional[str] = None
    research_objective: Optional[str] = None
    methodology: Optional[str] = None
    key_findings: Optional[str] = None
    limitations: Optional[str] = None
    relevance: Optional[str] = None
    apa_reference: Optional[str] = None


class LiteratureMetadataUpdate(BaseModel):
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    paper_type: Optional[str] = None
    edition: Optional[str] = None
    issn: Optional[str] = None
    isbn: Optional[str] = None


class LiteratureCandidateApply(BaseModel):
    index: int


class LiteratureRegenerateRequest(BaseModel):
    paper_ids: Optional[List[str]] = None
