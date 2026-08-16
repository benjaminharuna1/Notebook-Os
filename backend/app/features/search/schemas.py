from pydantic import BaseModel
from typing import List, Optional


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    document_ids: Optional[List[str]] = None
    project_id: Optional[str] = None
    include_keyword: bool = True


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_id: str
    document_title: str
    page_number: int
    source: str = "semantic"


class SearchResponse(BaseModel):
    results: List[SearchResult]
