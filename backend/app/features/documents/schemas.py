from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Document(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None


class DocumentList(BaseModel):
    documents: List[Document]
    total: int
    page: int
