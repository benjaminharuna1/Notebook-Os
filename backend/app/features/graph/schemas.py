from pydantic import BaseModel
from typing import List, Optional


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    weight: float = 1.0


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    weight: float = 1.0


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
